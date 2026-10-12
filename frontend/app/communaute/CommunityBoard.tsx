"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ArrowUpRight, MapPin, Search, X, Zap } from "lucide-react";
import { AliceAvatar } from "@/app/onboarding/components/AliceSilhouette";
import {
  applyDestination,
  rememberTargetOffer,
  type CommunityKind,
  type CommunityList,
  type CommunityOffer,
} from "@/lib/community";

const PAGE = 60;

const KINDS: { value: CommunityKind; label: string }[] = [
  { value: "alternance", label: "Alternances" },
  { value: "stage", label: "Stages" },
];

function formatDate(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

function normalize(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function CommunityBoard({ data }: { data: CommunityList | null }) {
  const router = useRouter();
  const offers = useMemo(() => data?.offers ?? [], [data]);

  const [kind, setKind] = useState<CommunityKind>("alternance");
  const [family, setFamily] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [onlyAlice, setOnlyAlice] = useState(false);
  const [onlyNew, setOnlyNew] = useState(false);
  const [shown, setShown] = useState(PAGE);
  /** Un filtre qui change ramène la liste à sa première page. */
  const refine = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setShown(PAGE);
  };
  const [chosen, setChosen] = useState<CommunityOffer | null>(null);

  const ofKind = useMemo(() => offers.filter((o) => o.kind === kind), [offers, kind]);

  const families = useMemo(() => {
    const counts = new Map<string, number>();
    for (const o of ofKind) counts.set(o.family, (counts.get(o.family) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => (a[0] === "Autres métiers" ? 1 : b[0] === "Autres métiers" ? -1 : b[1] - a[1]))
      .map(([name, count]) => ({ name, count }));
  }, [ofKind]);

  const filtered = useMemo(() => {
    const q = normalize(query.trim());
    const c = normalize(city.trim());
    return ofKind.filter(
      (o) =>
        (!family || o.family === family) &&
        (!onlyAlice || o.alice_sends) &&
        (!onlyNew || o.is_new) &&
        (!q || normalize(`${o.title} ${o.company}`).includes(q)) &&
        (!c || normalize(o.city).includes(c)),
    );
  }, [ofKind, family, onlyAlice, onlyNew, query, city]);

  const newCount = ofKind.filter((o) => o.is_new).length;
  const aliceCount = ofKind.filter((o) => o.alice_sends).length;

  const applyWithAlice = (offer: CommunityOffer) => {
    rememberTargetOffer({ id: offer.id, title: offer.title, company: offer.company });
    router.push(applyDestination());
  };

  return (
    <main className="min-h-[100dvh] bg-[#FAFAF8] text-[#1A1918]">
      {/* En-tête */}
      <header className="border-b border-[#1A1918]/[0.07]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <AliceAvatar size={28} />
            <span className="text-[15px] font-medium tracking-tight">
              Alice <span className="text-[#1A1918]/45">Community</span>
            </span>
          </Link>
          <Link
            href="/"
            className="rounded-full bg-[#1A1918] px-4 py-2 text-[13px] font-medium text-[#FAFAF8] transition hover:bg-[#006045]"
          >
            Essayer Alice
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-4 pb-6 pt-10 sm:px-6 sm:pt-14">
        <p className="text-[13px] font-medium text-[#006045]">Mise à jour chaque jour</p>
        <h1 className="mt-2 text-[32px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
          Alternances et stages 2027
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-[#1A1918]/65 sm:text-base">
          Toutes les offres qu&apos;Alice repère en France, chez France Travail, La bonne alternance et sur les
          sites carrière des entreprises. Gratuit, sans inscription. Et si tu veux, Alice adapte ton CV et ta
          lettre à l&apos;offre et postule pour toi.
        </p>

        {data && (
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-[#1A1918]/60">
            <span>
              <strong className="font-semibold text-[#1A1918]">{ofKind.length.toLocaleString("fr-FR")}</strong>{" "}
              offres
            </span>
            <span>
              <strong className="font-semibold text-[#1A1918]">{newCount.toLocaleString("fr-FR")}</strong>{" "}
              nouvelles en 48 h
            </span>
            {aliceCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Zap className="h-3.5 w-3.5 text-[#006045]" aria-hidden />
              <strong className="font-semibold text-[#1A1918]">{aliceCount.toLocaleString("fr-FR")}</strong>{" "}
              où Alice envoie elle-même
            </span>
            )}
          </div>
        )}
      </section>

      {/* Filtres */}
      <section className="sticky top-0 z-10 border-y border-[#1A1918]/[0.07] bg-[#FAFAF8]/95 backdrop-blur">
        <div className="mx-auto max-w-5xl space-y-3 px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-full bg-[#1A1918]/[0.05] p-1" role="tablist">
              {KINDS.map((k) => (
                <button
                  key={k.value}
                  role="tab"
                  aria-selected={kind === k.value}
                  onClick={() => {
                    refine(setKind)(k.value);
                    setFamily(null);
                  }}
                  className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
                    kind === k.value ? "bg-white text-[#1A1918] shadow-sm" : "text-[#1A1918]/55 hover:text-[#1A1918]"
                  }`}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <label className="relative min-w-0 flex-1 basis-40">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#1A1918]/35" />
              <input
                value={query}
                onChange={(e) => refine(setQuery)(e.target.value)}
                placeholder="Poste ou entreprise"
                aria-label="Rechercher un poste ou une entreprise"
                className="w-full rounded-full border border-[#1A1918]/10 bg-white py-2 pl-9 pr-3 text-[14px] outline-none placeholder:text-[#1A1918]/35 focus:border-[#006045]/50"
              />
            </label>
            <label className="relative min-w-0 flex-1 basis-32">
              <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#1A1918]/35" />
              <input
                value={city}
                onChange={(e) => refine(setCity)(e.target.value)}
                placeholder="Ville"
                aria-label="Filtrer par ville"
                className="w-full rounded-full border border-[#1A1918]/10 bg-white py-2 pl-9 pr-3 text-[14px] outline-none placeholder:text-[#1A1918]/35 focus:border-[#006045]/50"
              />
            </label>
          </div>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
            <Chip active={onlyAlice} onClick={() => refine(setOnlyAlice)(!onlyAlice)}>
              <Zap className="h-3.5 w-3.5" aria-hidden /> Alice envoie
            </Chip>
            <Chip active={onlyNew} onClick={() => refine(setOnlyNew)(!onlyNew)}>
              Nouvelles
            </Chip>
            <span className="mx-1 w-px shrink-0 bg-[#1A1918]/10" aria-hidden />
            {families.map((f) => (
              <Chip key={f.name} active={family === f.name} onClick={() => refine(setFamily)(family === f.name ? null : f.name)}>
                {f.name} <span className="opacity-50">{f.count}</span>
              </Chip>
            ))}
          </div>
        </div>
      </section>

      {/* Liste */}
      <section className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        {!data ? (
          <Empty title="La liste se met à jour" text="Reviens dans quelques minutes : Alice rassemble les offres du jour." />
        ) : filtered.length === 0 ? (
          <Empty title="Aucune offre avec ces filtres" text="Élargis la ville ou le métier, de nouvelles offres arrivent chaque jour." />
        ) : (
          <>
            <p className="mb-3 text-[13px] text-[#1A1918]/50">
              {filtered.length.toLocaleString("fr-FR")} offre{filtered.length > 1 ? "s" : ""}
            </p>
            <ul className="divide-y divide-[#1A1918]/[0.07] overflow-hidden rounded-2xl border border-[#1A1918]/[0.08] bg-white">
              {filtered.slice(0, shown).map((o) => (
                <OfferRow key={o.id} offer={o} onApply={() => setChosen(o)} />
              ))}
            </ul>
            {shown < filtered.length && (
              <div className="mt-5 flex justify-center">
                <button
                  onClick={() => setShown((n) => n + PAGE)}
                  className="rounded-full border border-[#1A1918]/12 bg-white px-5 py-2.5 text-[13px] font-medium transition hover:border-[#1A1918]/30"
                >
                  Voir plus d&apos;offres
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* Bandeau Alice */}
      <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
        <div className="flex flex-col items-start gap-4 rounded-2xl bg-[#1A1918] p-6 text-[#FAFAF8] sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div>
            <p className="text-lg font-semibold tracking-tight">Postuler une par une, c&apos;est un travail à plein temps.</p>
            <p className="mt-1 text-[14px] text-[#FAFAF8]/65">
              Alice adapte ton CV et ta lettre à chaque offre, et envoie pour toi. 3 candidatures offertes chaque semaine.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex shrink-0 items-center gap-2 rounded-full bg-[#FAFAF8] px-5 py-2.5 text-[14px] font-medium text-[#1A1918] transition hover:bg-white"
          >
            Commencer <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        {data && (
          <p className="mt-6 text-center text-[12px] text-[#1A1918]/40">
            Mise à jour le{" "}
            {new Date(data.updated_at).toLocaleString("fr-FR", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}{" "}
            · La source de chaque offre est indiquée, l&apos;annonce d&apos;origine fait foi.
          </p>
        )}
      </section>

      <AnimatePresence>
        {chosen && <ApplySheet offer={chosen} onClose={() => setChosen(null)} onApply={() => applyWithAlice(chosen)} />}
      </AnimatePresence>

      {/* Lien « Avec Alice » de la liste GitHub : /communaute?offre=<id>.
          Isolé sous Suspense : lire l'adresse ne prive pas la liste du rendu statique. */}
      <Suspense fallback={null}>
        <LinkedOffer offers={offers} onApply={applyWithAlice} />
      </Suspense>
    </main>
  );
}

function LinkedOffer({ offers, onApply }: { offers: CommunityOffer[]; onApply: (o: CommunityOffer) => void }) {
  const id = useSearchParams().get("offre");
  const [dismissed, setDismissed] = useState(false);
  const offer = id ? offers.find((o) => o.id === id) : undefined;
  return (
    <AnimatePresence>
      {offer && !dismissed && (
        <ApplySheet offer={offer} onClose={() => setDismissed(true)} onApply={() => onApply(offer)} />
      )}
    </AnimatePresence>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-[13px] transition ${
        active
          ? "border-[#006045] bg-[#006045] text-white"
          : "border-[#1A1918]/10 bg-white text-[#1A1918]/70 hover:border-[#1A1918]/25"
      }`}
    >
      {children}
    </button>
  );
}

function OfferRow({ offer, onApply }: { offer: CommunityOffer; onApply: () => void }) {
  return (
    <li className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-5">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-[14px] font-semibold">{offer.company}</span>
          {offer.is_new && (
            <span className="rounded-full bg-[#006045]/10 px-2 py-0.5 text-[11px] font-medium text-[#006045]">Nouveau</span>
          )}
          {offer.alice_sends && (
            <span className="inline-flex items-center gap-0.5 text-[11px] font-medium text-[#006045]" title="Alice peut envoyer cette candidature pour toi">
              <Zap className="h-3 w-3" aria-hidden /> Alice envoie
            </span>
          )}
        </div>
        <p className="mt-0.5 text-[15px] leading-snug text-[#1A1918]">{offer.title}</p>
        <p className="mt-1 text-[12.5px] text-[#1A1918]/50">
          {offer.city}
          {offer.remote === "remote" ? " · télétravail" : offer.remote === "hybrid" ? " · hybride" : ""} ·{" "}
          {formatDate(offer.published)} · {offer.source}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <a
          href={offer.url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="inline-flex items-center gap-1 rounded-full px-3 py-2 text-[13px] text-[#1A1918]/60 transition hover:text-[#1A1918]"
        >
          Annonce <ArrowUpRight className="h-3.5 w-3.5" />
        </a>
        <button
          onClick={onApply}
          className="rounded-full bg-[#1A1918] px-4 py-2 text-[13px] font-medium text-[#FAFAF8] transition hover:bg-[#006045]"
        >
          Postuler avec Alice
        </button>
      </div>
    </li>
  );
}

function ApplySheet({ offer, onClose, onApply }: { offer: CommunityOffer; onClose: () => void; onApply: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end justify-center bg-[#1A1918]/40 p-0 sm:items-center sm:p-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label={`Postuler chez ${offer.company}`}
        initial={{ y: 24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 24, opacity: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-md rounded-t-3xl bg-[#FAFAF8] p-6 shadow-xl sm:rounded-3xl"
      >
        <button onClick={onClose} aria-label="Fermer" className="absolute right-4 top-4 rounded-full p-1.5 text-[#1A1918]/40 hover:text-[#1A1918]">
          <X className="h-4 w-4" />
        </button>
        <AliceAvatar size={36} />
        <p className="mt-4 text-[13px] text-[#1A1918]/50">{offer.company} · {offer.city}</p>
        <h2 className="mt-1 text-lg font-semibold leading-snug tracking-tight">{offer.title}</h2>
        <ul className="mt-4 space-y-2 text-[14px] text-[#1A1918]/75">
          <li>Je lis l&apos;offre et j&apos;adapte ton CV à ce poste.</li>
          <li>J&apos;écris une lettre de motivation qui parle de l&apos;entreprise.</li>
          <li>
            {offer.alice_sends
              ? "J'envoie la candidature pour toi."
              : "Je te prépare tout pour finir sur le site en un clic."}
          </li>
        </ul>
        <button
          onClick={onApply}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#006045] px-5 py-3 text-[14px] font-medium text-white transition hover:bg-[#004d37]"
        >
          Postuler avec Alice <ArrowRight className="h-4 w-4" />
        </button>
        <p className="mt-3 text-center text-[12px] text-[#1A1918]/45">Gratuit · 3 candidatures offertes chaque semaine</p>
        <a
          href={offer.url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="mt-3 block text-center text-[12.5px] text-[#1A1918]/55 underline-offset-2 hover:underline"
        >
          Voir l&apos;annonce d&apos;origine
        </a>
      </motion.div>
    </motion.div>
  );
}

function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-[#1A1918]/12 px-6 py-14 text-center">
      <p className="text-[15px] font-medium">{title}</p>
      <p className="mt-1 text-[13px] text-[#1A1918]/55">{text}</p>
    </div>
  );
}
