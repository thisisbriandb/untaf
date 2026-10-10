"""
Alice rend compte par e-mail.

C'est ce qui tient la promesse « confie-moi une mission et va faire autre
chose » : sans notification, il fallait revenir dans l'application pour
découvrir qu'une mission était finie ou que des candidatures attendaient.

Trois règles :
  - le candidat décide de ce qu'il reçoit (`notification_prefs`), et peut
    tout couper ;
  - rien n'est envoyé deux fois : chaque notification porte une clé unique,
    vérifiée avant l'envoi et garantie par la base ;
  - notifier ne fait jamais échouer l'action notifiée. Une mission terminée
    reste terminée même si le service d'e-mail est en panne.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.agents.company_name import chez, display_company
from app.agents.notifications.mailer import deliver
from app.agents.notifications.templates import Email, Item, render_html, render_text
from app.config import settings
from app.database import async_session
from app.models.candidate import Candidate
from app.models.notification import Notification, NotificationKind, NotificationStatus

logger = logging.getLogger(__name__)

#: Réglages appliqués tant que le candidat n'a rien choisi. Le rapport de
#: mission et la file de validation sont actifs : ce sont les deux moments où
#: l'absence de message coûte quelque chose au candidat.
DEFAULT_PREFS: dict = {
    "enabled": True,
    "mission_report": True,
    "application_sent": True,
    "awaiting_approval": True,
    "followups": True,
    "digest": "weekly",  # off | daily | weekly
}

DIGEST_PERIODS = ("off", "daily", "weekly")

#: Réglage qui commande chaque type de notification. Le test passe toujours :
#: c'est le candidat qui le demande.
_PREF_FOR_KIND = {
    NotificationKind.MISSION_REPORT: "mission_report",
    NotificationKind.APPLICATION_SENT: "application_sent",
    NotificationKind.AWAITING_APPROVAL: "awaiting_approval",
    NotificationKind.FOLLOWUP_DUE: "followups",
}


def resolve_prefs(candidate: Candidate | None) -> dict:
    """Préférences effectives : celles du candidat, complétées par les défauts."""
    stored = (candidate.notification_prefs or {}) if candidate else {}
    prefs = {**DEFAULT_PREFS, **{k: v for k, v in stored.items() if k in DEFAULT_PREFS}}
    if prefs["digest"] not in DIGEST_PERIODS:
        prefs["digest"] = DEFAULT_PREFS["digest"]
    return prefs


def _allowed(prefs: dict, kind: NotificationKind) -> bool:
    if kind == NotificationKind.TEST:
        return True
    if not prefs.get("enabled"):
        return False
    if kind == NotificationKind.DIGEST:
        return prefs.get("digest") != "off"
    return bool(prefs.get(_PREF_FOR_KIND.get(kind, ""), True))


def link(tab: str | None = None) -> str:
    base = settings.frontend_url.rstrip("/") + "/dashboard"
    return f"{base}?tab={tab}" if tab else base


FOOTER = (
    "Tu reçois ce message parce qu'Alice travaille pour toi. Tu choisis ce "
    "qu'elle t'écrit dans Paramètres → Notifications."
)


async def _send(
    candidate_id: UUID,
    kind: NotificationKind,
    dedupe_key: str,
    email: Email,
    payload: dict | None = None,
) -> Notification | None:
    """
    Envoie si les préférences le permettent et si ce n'est pas déjà fait.
    Ne lève jamais. Renvoie la trace enregistrée, ou None si rien n'a été tenté.
    """
    try:
        async with async_session() as session:
            candidate = await session.get(Candidate, candidate_id)
            if not candidate or not candidate.email:
                return None
            if not _allowed(resolve_prefs(candidate), kind):
                return None
            already = (await session.execute(
                select(Notification.id).where(Notification.dedupe_key == dedupe_key)
            )).scalar_one_or_none()
            if already:
                return None
            recipient = candidate.email

        result = await deliver(recipient, email.subject, render_html(email), render_text(email))

        status = (
            NotificationStatus.SENT if result["ok"] and result["real"]
            else NotificationStatus.SIMULATED if result["ok"]
            else NotificationStatus.FAILED
        )
        record = Notification(
            candidate_id=candidate_id,
            kind=kind,
            status=status,
            dedupe_key=dedupe_key[:200],
            subject=email.subject[:300],
            recipient=recipient,
            error=result.get("error"),
            payload={**(payload or {}), "provider": result.get("provider"),
                     "provider_id": result.get("id")},
        )
        async with async_session() as session:
            session.add(record)
            try:
                await session.commit()
            except IntegrityError:
                # Deux clôtures concurrentes : l'autre a déjà enregistré.
                await session.rollback()
                return None
        if status == NotificationStatus.FAILED:
            from app.agents.incidents import report_incident
            await report_incident(
                "notification_failed", candidate_id, result.get("error") or "",
                context={"kind": kind.value, "subject": email.subject},
            )
        return record
    except Exception as e:  # noqa: BLE001 — notifier ne casse jamais l'action
        logger.error("Notification %s impossible : %s", kind.value, e, exc_info=True)
        return None


# ── Fin de mission ─────────────────────────────────────────────────────────


async def notify_mission_report(run_id: UUID) -> Notification | None:
    from app.models.mission import Mission, MissionEvent, MissionEventKind, MissionRun, RunStatus
    from app.models.dispatch import ApplicationDispatch, DispatchStatus
    from app.models.mission import Mission, MissionRun, RunStatus

    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        if not run:
            return None
        candidate_id = (await session.execute(
            select(Mission.candidate_id).where(Mission.id == run.mission_id)
        )).scalar_one_or_none()
        if not candidate_id:
            return None
        waiting = (await session.execute(
            select(ApplicationDispatch)
            .where(ApplicationDispatch.run_id == run_id)
            .where(ApplicationDispatch.status == DispatchStatus.AWAITING_APPROVAL)
            .order_by(ApplicationDispatch.created_at)
            .limit(8)
        )).scalars().all()
        sent = (await session.execute(
            select(ApplicationDispatch)
            .where(ApplicationDispatch.run_id == run_id)
            .where(ApplicationDispatch.status == DispatchStatus.SENT)
            .limit(8)
        )).scalars().all()
        to_finish = (await session.execute(
            select(ApplicationDispatch)
            .where(ApplicationDispatch.run_id == run_id)
            .where(ApplicationDispatch.status == DispatchStatus.PREPARED)
            .order_by(ApplicationDispatch.created_at)
            .limit(8)
        )).scalars().all()
        prepared = (await session.execute(
            select(MissionEvent)
            .where(MissionEvent.run_id == run_id)
            .where(MissionEvent.kind == MissionEventKind.LETTER_WRITTEN)
            .order_by(MissionEvent.created_at)
            .limit(10)
        )).scalars().all()
        stats = dict(run.stats or {})
        title, report, completed = run.title, run.report, run.status == RunStatus.COMPLETED

    items = [Item(d.job_title, display_company(d.company_name) or "", "à valider") for d in waiting]
    items += [Item(d.job_title, display_company(d.company_name) or "", "envoyée") for d in sent]
    items += [Item(d.job_title, display_company(d.company_name) or "", "à finir sur le site")
              for d in to_finish]
    if not items:
        # Mission « préparer » : rien n'est parti, mais chaque dossier est là.
        items = [
            Item((e.payload or {}).get("job_title") or e.summary,
                 display_company((e.payload or {}).get("company")) or "", "dossier prêt")
            for e in prepared
        ]
    n_wait = stats.get("awaiting_approval", 0)
    n_packs = stats.get("packs", stats.get("letters", 0))

    email = Email(
        subject=(
            f"Mission terminée — {n_wait} candidature{'s' if n_wait > 1 else ''} à valider"
            if n_wait else f"Mission terminée : {title}"
        ) if completed else f"Mission interrompue : {title}",
        preheader=(report or "")[:140],
        heading="J'ai terminé ma mission." if completed else "Ma mission s'est arrêtée.",
        paragraphs=[report] if report else [],
        stats=[
            (stats.get("scanned", 0), "offres vues"),
            (stats.get("shortlisted", 0), "retenues"),
            (stats.get("packs", stats.get("letters", 0)), "packs prêts"),
            (stats.get("sent", 0), "envoyées"),
        ],
        items_title="Ce qui t'attend" if items else "",
        items=items,
        cta_label=("Valider mes candidatures" if n_wait
                   else "Voir mes dossiers" if n_packs else "Voir le détail"),
        cta_url=link("candidatures" if n_wait or n_packs else "mission"),
        footer=FOOTER,
    )
    return await _send(
        candidate_id, NotificationKind.MISSION_REPORT, f"mission_report:{run_id}", email,
        {"run_id": str(run_id), "stats": stats},
    )


# ── Candidature partie ─────────────────────────────────────────────────────


async def notify_application_sent(candidate_id: UUID, dispatch_id: UUID) -> Notification | None:
    """Confirmation d'un envoi RÉEL — jamais d'une répétition."""
    from app.models.dispatch import ApplicationDispatch, DispatchStatus

    async with async_session() as session:
        dispatch = await session.get(ApplicationDispatch, dispatch_id)
        if not dispatch or dispatch.status != DispatchStatus.SENT:
            return None
        title, company = dispatch.job_title, dispatch.company_name
        channel = dispatch.channel.value
        destination = dispatch.destination

    via = f"par e-mail à {destination}" if channel == "email" else "via le formulaire de l'employeur"
    email = Email(
        subject=f"Candidature envoyée{chez(company)}" if display_company(company) else f"Candidature envoyée : {title}",
        preheader=f"« {title} » — partie {via}.",
        heading=f"Ta candidature est partie{chez(company)}.",
        paragraphs=[
            f"J'ai envoyé ta candidature pour « {title} » {via}, avec ton CV adapté "
            f"et ta lettre.",
            f"Si rien ne bouge d'ici {settings.followup_after_days} jours, je te "
            f"proposerai une relance déjà rédigée.",
        ],
        cta_label="Voir la candidature",
        cta_url=link("candidatures"),
        footer=FOOTER,
    )
    return await _send(
        candidate_id, NotificationKind.APPLICATION_SENT, f"application_sent:{dispatch_id}",
        email, {"dispatch_id": str(dispatch_id)},
    )


# ── Dossiers en attente ────────────────────────────────────────────────────

#: Rappels pour un même lot de dossiers en attente : J+1 puis J+4, puis on se
#: tait. Au-delà, la relance devient du harcèlement.
PENDING_REMINDER_DAYS = (1, 4)


async def notify_pending(candidate_id: UUID) -> Notification | None:
    """
    Des dossiers attendent le candidat : son feu vert, ou un geste sur le site
    de l'employeur. Sans relance, ils ne partent jamais — et le candidat ne
    voit jamais Alice postuler pour lui.
    """
    from app.models.application import Application, ApplicationStatus
    from app.models.dispatch import ApplicationDispatch, DispatchStatus

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        rows = (await session.execute(
            select(ApplicationDispatch)
            .join(Application, Application.id == ApplicationDispatch.application_id)
            .where(ApplicationDispatch.candidate_id == candidate_id)
            .where(ApplicationDispatch.status.in_((
                DispatchStatus.AWAITING_APPROVAL, DispatchStatus.PREPARED,
            )))
            .where(Application.status.notin_((
                ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW,
                ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.CLOSED,
            )))
            .order_by(ApplicationDispatch.created_at)
        )).scalars().all()
    if not rows:
        return None

    oldest = rows[0]
    created = oldest.created_at if oldest.created_at.tzinfo else oldest.created_at.replace(tzinfo=timezone.utc)
    age = (now - created).days
    step = sum(1 for d in PENDING_REMINDER_DAYS if age >= d)
    if step == 0:
        return None

    waiting = [d for d in rows if d.status == DispatchStatus.AWAITING_APPROVAL]
    to_finish = [d for d in rows if d.status == DispatchStatus.PREPARED]
    n_wait, n_finish = len(waiting), len(to_finish)

    parts = []
    if n_wait:
        parts.append(f"{n_wait} candidature{'s' if n_wait > 1 else ''} à valider")
    if n_finish:
        parts.append(f"{n_finish} à finir sur le site")
    paragraphs = []
    if n_wait:
        paragraphs.append(
            f"{'Elles sont prêtes' if n_wait > 1 else 'Elle est prête'} : CV adapté, lettre signée. "
            "Un clic sur « Tout valider » et je les envoie."
        )
    if n_finish:
        paragraphs.append(
            "Pour les autres, l'employeur a son propre formulaire : ton dossier est prêt, "
            "« Finir sur le site » le remplit avec toi en un geste."
        )
    if step == len(PENDING_REMINDER_DAYS):
        paragraphs.append("Je ne t'en reparlerai plus : tes dossiers restent dans Candidatures.")

    email = Email(
        subject=" et ".join(parts).capitalize(),
        preheader="Tes dossiers sont prêts, il ne manque que toi.",
        heading="Tes candidatures n'attendent plus que toi.",
        paragraphs=paragraphs,
        items=(
            [Item(d.job_title, display_company(d.company_name) or "", "à valider") for d in waiting[:6]]
            + [Item(d.job_title, display_company(d.company_name) or "", "à finir sur le site")
               for d in to_finish[:6]]
        ),
        cta_label="Tout valider" if n_wait else "Finir mes candidatures",
        cta_url=link("candidatures"),
        footer=FOOTER,
    )
    return await _send(
        candidate_id, NotificationKind.AWAITING_APPROVAL,
        f"pending:{candidate_id}:{oldest.id}:{step}", email,
        {"awaiting": n_wait, "to_finish": n_finish, "step": step},
    )


# ── Relances ───────────────────────────────────────────────────────────────


async def notify_followups_due(candidate_id: UUID, due: list[dict]) -> Notification | None:
    """
    Une seule notification pour toutes les relances du jour : un e-mail par
    candidature à relancer serait du bruit.
    """
    if not due:
        return None
    n = len(due)
    today = datetime.now(timezone.utc).date().isoformat()
    email = Email(
        subject=f"{n} relance{'s' if n > 1 else ''} à envoyer",
        preheader="Les messages sont rédigés, il ne reste qu'à les relire.",
        heading=(
            f"{n} candidature{'s' if n > 1 else ''} sans réponse depuis "
            f"{settings.followup_after_days} jours."
        ),
        paragraphs=[
            "Une relance courte et polie augmente nettement les chances de réponse. "
            "J'ai rédigé chaque message : relis-le et envoie-le en un clic.",
        ],
        items=[
            Item(d["job_title"], d["company_name"], f"envoyée il y a {d['days']} j")
            for d in due[:10]
        ],
        cta_label="Voir les relances",
        cta_url=link("candidatures"),
        footer=FOOTER,
    )
    return await _send(
        candidate_id, NotificationKind.FOLLOWUP_DUE, f"followup_due:{candidate_id}:{today}",
        email, {"applications": [d["application_id"] for d in due]},
    )


# ── Rapport périodique ─────────────────────────────────────────────────────


async def send_digest(candidate_id: UUID, period: str) -> Notification | None:
    """Rapport d'activité : ce qu'Alice a fait depuis le précédent."""
    from app.models.application import Application, ApplicationStatus
    from app.models.dispatch import ApplicationDispatch, DispatchStatus
    from app.models.mission import Mission, MissionEvent

    days = 1 if period == "daily" else 7
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate or resolve_prefs(candidate)["digest"] != period:
            return None

        new_matches = (await session.execute(
            select(func.count(Application.id))
            .where(Application.candidate_id == candidate_id)
            .where(Application.created_at >= since)
            .where(Application.status == ApplicationStatus.MATCHED)
        )).scalar() or 0
        dispatch_rows = (await session.execute(
            select(ApplicationDispatch.status, func.count(ApplicationDispatch.id))
            .where(ApplicationDispatch.candidate_id == candidate_id)
            .where(ApplicationDispatch.created_at >= since)
            .group_by(ApplicationDispatch.status)
        )).all()
        waiting_total = (await session.execute(
            select(func.count(ApplicationDispatch.id))
            .where(ApplicationDispatch.candidate_id == candidate_id)
            .where(ApplicationDispatch.status == DispatchStatus.AWAITING_APPROVAL)
        )).scalar() or 0
        interviews = (await session.execute(
            select(func.count(Application.id))
            .where(Application.candidate_id == candidate_id)
            .where(Application.status.in_([ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER]))
        )).scalar() or 0
        raw_events = (await session.execute(
            select(MissionEvent.summary)
            .join(Mission, Mission.id == MissionEvent.mission_id)
            .where(Mission.candidate_id == candidate_id)
            .where(MissionEvent.created_at >= since)
            .order_by(MissionEvent.created_at.desc())
            .limit(40)
        )).scalars().all()
        # Une même alerte répétée trois fois ne dit rien de plus.
        events = list(dict.fromkeys(e for e in raw_events if e))[:6]

        # Les dossiers prêts, pas encore partis : ce que le point doit montrer.
        from app.models.company import Company
        from app.models.job_posting import JobPosting
        ready_rows = (await session.execute(
            select(Application, JobPosting.title, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.candidate_id == candidate_id)
            .where(Application.status.in_([ApplicationStatus.MATCHED, ApplicationStatus.PENDING]))
            .where(Application.metadata_json.has_key("cover_letter"))
            .order_by(Application.match_score.desc())
        )).all()
        packs_ready = len(ready_rows)
        top_items = [Item(title, display_company(company) or "", "dossier prêt")
                     for _, title, company in ready_rows[:5]]

        # Formule gratuite : ce que l'abonnement débloquerait, chiffré sur sa
        # propre recherche (offres retenues qui attendent encore leur dossier).
        from app import billing
        upsell = None
        if billing.settings.billing_enabled:
            _, paid = await billing.limits_for(session, candidate_id)
            if not paid:
                waiting_packs = (await session.execute(
                    select(func.count(Application.id))
                    .where(Application.candidate_id == candidate_id)
                    .where(Application.status == ApplicationStatus.MATCHED)
                    .where(~Application.metadata_json.has_key("cover_letter"))
                )).scalar() or 0
                upsell = (
                    (f"{waiting_packs} offre{'s' if waiting_packs > 1 else ''} retenue"
                     f"{'s' if waiting_packs > 1 else ''} pour toi attend{'ent' if waiting_packs > 1 else ''} "
                     f"encore {'leur' if waiting_packs > 1 else 'son'} dossier. " if waiting_packs else "")
                    + f"Avec l'abonnement ({billing.settings.billing_price_label}, sans engagement), je "
                    f"envoie jusqu'à {billing.settings.paid_sends_per_week} candidatures par semaine et "
                    f"j'écris à {billing.settings.spontaneous_weekly_cap} entreprises qui recrutent sans annonce."
                )

    by_status = {s: n for s, n in dispatch_rows}
    sent = by_status.get(DispatchStatus.SENT, 0)

    # Une semaine sans rien à raconter ne mérite pas un e-mail.
    if not (new_matches or sent or waiting_total or events or packs_ready):
        return None

    label = "aujourd'hui" if period == "daily" else "cette semaine"
    paragraphs = [f"Voici ce que j'ai fait pour toi {label}."]
    if waiting_total:
        paragraphs.append(
            f"{waiting_total} candidature{'s attendent' if waiting_total > 1 else ' attend'} "
            f"ton feu vert."
        )
    paragraphs += [f"— {e}" for e in events[:4]]
    if upsell:
        paragraphs.append(upsell)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d" if period == "daily" else "%G-W%V")
    email = Email(
        subject=f"Ton point {'du jour' if period == 'daily' else 'de la semaine'} avec Alice",
        preheader=f"{packs_ready} dossiers prêts, {sent} candidatures envoyées.",
        heading=f"Ton point {'du jour' if period == 'daily' else 'de la semaine'}.",
        paragraphs=paragraphs,
        stats=[
            (packs_ready, "dossiers prêts"),
            (sent, "envoyées"),
            (waiting_total, "à valider"),
            (interviews, "entretiens"),
        ],
        items_title="Tes dossiers prêts" if top_items else "",
        items=top_items,
        cta_label="Ouvrir mon espace",
        cta_url=link("candidatures" if waiting_total or packs_ready else None),
        footer=FOOTER,
    )
    return await _send(
        candidate_id, NotificationKind.DIGEST, f"digest:{period}:{candidate_id}:{stamp}", email,
        {"period": period},
    )


async def send_digests(period: str) -> int:
    """Rapport pour tous les candidats abonnés à cette période."""
    async with async_session() as session:
        ids = (await session.execute(select(Candidate.id))).scalars().all()
    sent = 0
    for candidate_id in ids:
        if await send_digest(candidate_id, period):
            sent += 1
    return sent


# ── Essai ──────────────────────────────────────────────────────────────────


async def send_test(candidate_id: UUID) -> Notification | None:
    """Envoi d'essai, demandé depuis les paramètres."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    email = Email(
        subject="Alice peut t'écrire",
        preheader="Les notifications fonctionnent.",
        heading="Les notifications fonctionnent.",
        paragraphs=[
            "C'est par ici que je te préviendrai quand une mission se termine, "
            "quand une candidature attend ton accord ou quand il est temps de relancer.",
        ],
        cta_label="Ouvrir mon espace",
        cta_url=link(),
        footer=FOOTER,
    )
    return await _send(candidate_id, NotificationKind.TEST, f"test:{candidate_id}:{stamp}", email)
