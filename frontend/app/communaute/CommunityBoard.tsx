"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ArrowUpRight, MapPin, Search, X, Zap } from "lucide-react";
import { AliceAvatar } from "@/app/onboarding/components/AliceSilhouette";
import {
  applyDestination,
  DEFAULT_FILTERS,
  fetchCommunityOffer,
  fetchCommunityPage,
  rememberTargetOffer,
  type CommunityFilters,
  type CommunityKind,
  type CommunityOffer,
  type CommunityPage,
} from "@/lib/community";

const KINDS: { value: CommunityKind; label: string }[] = [
  { value: "alternance", label: "Alternances" },
  { value: "stage", label: "Stages" },
  { value: "emploi", label: "Premier emploi" },
];

const KIND_HINT: Record<CommunityKind, string> = {
  alternance: "",
  stage: "",
  emploi: "CDI et CDD ouverts aux débutants et jeunes diplômés (2 ans d'expérience au plus).",
};

function formatDate(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

const keyOf = (f: CommunityFilters) => JSON.stringify(f);

interface Results {
  key: string;
  pages: CommunityPage[];
  failed?: boolean;
}

export function CommunityBoard({ initial }: { initial: CommunityPage | null }) {
  const router = useRouter();
  const [filters, setFilters] = useState<CommunityFilters>(DEFAULT_FILTERS);
  // Le texte tapé n'interroge l'API qu'après une courte pause.
  const [typed, setTyped] = useState({ q: "", city: "" });
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: typed.q, city: typed.city })), 300);
    return () => clearTimeout(t);
  }, [typed]);

  const key = keyOf(filters);
  // Première page rendue par le serveur ; ensuite, une recherche par jeu de filtres.
  const [results, setResults] = useState<Results>(() => ({
    key: initial ? keyOf(DEFAULT_FILTERS) : "",
    pages: initial ? [initial] : [],
  }));
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    if (results.key === key) return;
    let alive = true;
    fetchCommunityPage(filters).then((page) => {
      if (alive) setResults(page ? { key, pages: [page] } : { key, pages: [], failed: true });
    });
    return () => {
      alive = false;
    };
  }, [key, filters, results.key]);

  const loading = results.key !== key;
  const head = results.pages[0] ?? null;
  const offers = results.pages.flatMap((p) => p.offers);
  const hasMore = head ? offers.length < head.matched : false;

  const loadMore = () => {
    if (!head || loadingMore) return;
    setLoadingMore(true);
    fetchCommunityPage(filters, results.pages.length + 1).then((page) => {
      setLoadingMore(false);
      if (page) setResults((r) => (r.key === key ? { ...r, pages: [...r.pages, page] } : r));
    });
  };

  const set = (patch: Partial<CommunityFilters>) => setFilters((f) => ({ ...f, ...patch }));
  const [chosen, setChosen] = useState<CommunityOffer | null>(null);

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
              Alice <span className="text-[#6B6B68]">Community</span>
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
          Alternances, stages et premiers emplois
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-[#1A1918]/65 sm:text-base">
          Toutes les offres qu&apos;Alice repère en France pour les étudiants et jeunes diplômés : France Travail,
          les sites carrière des entreprises et des agrégateurs comme Adzuna. Gratuit, sans
          inscription. Et si tu veux, Alice adapte ton CV et ta lettre à l&apos;offre et postule pour toi.
        </p>

        {head && (
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-[#1A1918]/60">
            <span>
              <strong className="font-semibold text-[#1A1918]">{head.total.toLocaleString("fr-FR")}</strong> offres
            </span>
            <span>
              <strong className="font-semibold text-[#1A1918]">{head.new_count.toLocaleString("fr-FR")}</strong>{" "}
              nouvelles en 48 h
            </span>
            {head.alice_count > 0 && (
              <span className="inline-flex items-center gap-1">
                <Zap className="h-3.5 w-3.5 text-[#006045]" aria-hidden />
                <strong className="font-semibold text-[#1A1918]">{head.alice_count.toLocaleString("fr-FR")}</strong>{" "}
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
            <div className="-mx-4 flex max-w-[calc(100%+2rem)] overflow-x-auto px-4 sm:mx-0 sm:px-0">
              <div className="flex shrink-0 rounded-full bg-[#1A1918]/[0.05] p-1" role="tablist">
                {KINDS.map((k) => (
                  <button
                    key={k.value}
                    role="tab"
                    aria-selected={filters.kind === k.value}
                    onClick={() => set({ kind: k.value, family: null })}
                    className={`whitespace-nowrap rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
                      filters.kind === k.value
                        ? "bg-white text-[#1A1918] shadow-sm"
                        : "text-[#6B6B68] hover:text-[#1A1918]"
                    }`}
                  >
                    {k.label}
                  </button>
                ))}
              </div>
            </div>
            <label className="relative min-w-0 flex-1 basis-40">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B6B68]" />
              <input
                value={typed.q}
                onChange={(e) => setTyped((t) => ({ ...t, q: e.target.value }))}
                placeholder="Poste ou entreprise"
                aria-label="Rechercher un poste ou une entreprise"
                className="w-full rounded-full border border-[#1A1918]/10 bg-white py-2 pl-9 pr-3 text-[14px] outline-none placeholder:text-[#6B6B68] focus:border-[#006045]/50"
              />
            </label>
            <label className="relative min-w-0 flex-1 basis-32">
              <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B6B68]" />
              <input
                value={typed.city}
                onChange={(e) => setTyped((t) => ({ ...t, city: e.target.value }))}
                placeholder="Ville"
                aria-label="Filtrer par ville"
                className="w-full rounded-full border border-[#1A1918]/10 bg-white py-2 pl-9 pr-3 text-[14px] outline-none placeholder:text-[#6B6B68] focus:border-[#006045]/50"
              />
            </label>
          </div>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
            <Chip active={filters.alice} onClick={() => set({ alice: !filters.alice })}>
              <Zap className="h-3.5 w-3.5" aria-hidden /> Alice envoie
            </Chip>
            <Chip active={filters.fresh} onClick={() => set({ fresh: !filters.fresh })}>
              Nouvelles
            </Chip>
            <Chip active={filters.direct} onClick={() => set({ direct: !filters.direct })}>
              Employeurs directs
            </Chip>
            <span className="mx-1 w-px shrink-0 bg-[#1A1918]/10" aria-hidden />
            {(head?.families ?? []).map((f) => (
              <Chip
                key={f.name}
                active={filters.family === f.name}
                onClick={() => set({ family: filters.family === f.name ? null : f.name })}
              >
                {f.name} <span className="opacity-50">{f.count}</span>
              </Chip>
            ))}
          </div>
        </div>
      </section>

      {/* Liste */}
      <section className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        {KIND_HINT[filters.kind] && <p className="mb-3 text-[13px] text-[#6B6B68]">{KIND_HINT[filters.kind]}</p>}
        {!head ? (
          results.failed ? (
            <Empty title="La liste ne répond pas" text="Réessaie dans un instant : Alice rassemble les offres du jour." />
          ) : (
            <Empty title="Chargement des offres…" text="Alice rassemble les offres du jour." />
          )
        ) : head.matched === 0 ? (
          <Empty title="Aucune offre avec ces filtres" text="Élargis la ville ou le métier, de nouvelles offres arrivent chaque jour." />
        ) : (
          <div className={loading ? "opacity-50 transition-opacity" : "transition-opacity"} aria-busy={loading}>
            <p className="mb-3 text-[13px] text-[#6B6B68]">
              {head.matched.toLocaleString("fr-FR")} offre{head.matched > 1 ? "s" : ""}
            </p>
            <ul className="divide-y divide-[#1A1918]/[0.07] overflow-hidden rounded-2xl border border-[#1A1918]/[0.08] bg-white">
              {offers.map((o) => (
                <OfferRow key={o.id} offer={o} onApply={() => setChosen(o)} />
              ))}
            </ul>
            {hasMore && (
              <div className="mt-5 flex justify-center">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="rounded-full border border-[#1A1918]/12 bg-white px-5 py-2.5 text-[13px] font-medium transition hover:border-[#1A1918]/30 disabled:opacity-60"
                >
                  {loadingMore ? "Chargement…" : "Voir plus d'offres"}
                </button>
              </div>
            )}
          </div>
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
        {head && (
          <p className="mt-6 text-center text-[12px] text-[#6B6B68]">
            Mise à jour le{" "}
            {new Date(head.updated_at).toLocaleString("fr-FR", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}{" "}
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
        <LinkedOffer onApply={applyWithAlice} />
      </Suspense>
    </main>
  );
}

function LinkedOffer({ onApply }: { onApply: (o: CommunityOffer) => void }) {
  const id = useSearchParams().get("offre");
  const [offer, setOffer] = useState<CommunityOffer | null>(null);
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    if (!id) return;
    let alive = true;
    fetchCommunityOffer(id).then((o) => {
      if (alive) setOffer(o);
    });
    return () => {
      alive = false;
    };
  }, [id]);
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
          {offer.via_school && (
            <span
              className="rounded-full bg-[#1A1918]/[0.06] px-2 py-0.5 text-[11px] font-medium text-[#1A1918]/60"
              title="Une école ou un CFA recrute pour une entreprise partenaire : tu t'inscris à sa formation."
            >
              Via un CFA
            </span>
          )}
          {offer.alice_sends && (
            <span className="inline-flex items-center gap-0.5 text-[11px] font-medium text-[#006045]" title="Alice peut envoyer cette candidature pour toi">
              <Zap className="h-3 w-3" aria-hidden /> Alice envoie
            </span>
          )}
        </div>
        <p className="mt-0.5 text-[15px] leading-snug text-[#1A1918]">{offer.title}</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-1 gap-y-1 text-[12.5px] text-[#6B6B68]">
          <span>
            {offer.city}
            {offer.other_cities ? ` et ${offer.other_cities} autre${offer.other_cities > 1 ? "s" : ""} ville${offer.other_cities > 1 ? "s" : ""}` : ""}
            {offer.remote === "remote" ? " · télétravail" : offer.remote === "hybrid" ? " · hybride" : ""} ·{" "}
            {formatDate(offer.published)}
            {offer.attribution_label ? " · via" : ` · ${offer.source}`}
          </span>
          {offer.attribution_label && offer.attribution_url && (
            // Mention exigée par l'agrégateur : son nom, lié à son site, 116 × 23 px au moins.
            <a
              href={offer.attribution_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-[23px] min-w-[116px] items-center justify-center rounded-md border border-[#1A1918]/12 bg-[#FAFAF8] px-2 text-[12px] font-semibold text-[#1A1918]/70 hover:text-[#1A1918]"
            >
              {offer.attribution_label}
            </a>
          )}
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
        <button onClick={onClose} aria-label="Fermer" className="absolute right-4 top-4 rounded-full p-1.5 text-[#6B6B68] hover:text-[#1A1918]">
          <X className="h-4 w-4" />
        </button>
        <AliceAvatar size={36} />
        <p className="mt-4 flex flex-wrap items-center gap-1 text-[13px] text-[#6B6B68]">
          <span>{offer.company} · {offer.city}</span>
          {offer.attribution_label && offer.attribution_url && (
            <>
              <span>· via</span>
              <a
                href={offer.attribution_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-[23px] min-w-[116px] items-center justify-center rounded-md border border-[#1A1918]/12 px-2 text-[12px] font-semibold text-[#1A1918]/70"
              >
                {offer.attribution_label}
              </a>
            </>
          )}
        </p>
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
        <p className="mt-3 text-center text-[12px] text-[#6B6B68]">Gratuit · 3 candidatures offertes chaque semaine</p>
        <a
          href={offer.url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="mt-3 block text-center text-[12.5px] text-[#6B6B68] underline-offset-2 hover:underline"
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
      <p className="mt-1 text-[13px] text-[#6B6B68]">{text}</p>
    </div>
  );
}
