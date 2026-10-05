"use client";

import { motion } from "framer-motion";
import { ArrowRight, Loader2, MapPin, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Le mandat de recherche, demandé juste avant le pacte final.
 *
 * Seule la zone est obligatoire : c'est le filtre dur qui évite de proposer
 * des offres allemandes à quelqu'un qui cherche à Paris. Tout le reste peut
 * rester vide — le backend déduit du profil ce qui n'est pas dit.
 */

export const EU_COUNTRIES = [
  "FR", "BE", "CH", "LU", "DE", "ES", "IT", "PT", "NL", "IE",
  "AT", "DK", "SE", "NO", "FI", "PL", "CZ", "GB",
];

export type Zone = "france" | "europe" | "monde";

export const ZONE_COUNTRIES: Record<Zone, string[]> = {
  france: ["FR"],
  europe: EU_COUNTRIES,
  monde: [],
};

const ZONES: { id: Zone; label: string; hint: string }[] = [
  { id: "france", label: "France", hint: "et remote depuis la France" },
  { id: "europe", label: "Europe", hint: "espace européen" },
  { id: "monde", label: "Sans limite", hint: "partout" },
];

const COMMON_CITIES = [
  "Paris", "Lyon", "Bordeaux", "Nantes", "Lille",
  "Toulouse", "Marseille", "Rennes", "Montpellier",
];

const RHYTHMS = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybride" },
  { value: "onsite", label: "Sur site" },
];

const LANGUAGES = [
  { value: "fr", label: "Français" },
  { value: "en", label: "Anglais" },
  { value: "de", label: "Allemand" },
  { value: "es", label: "Espagnol" },
  { value: "it", label: "Italien" },
  { value: "nl", label: "Néerlandais" },
];

/** Libellés humains — la valeur envoyée reste la famille du moteur. */
const FAMILIES = [
  { value: "software", label: "Tech / Dév" },
  { value: "data", label: "Data / IA" },
  { value: "product", label: "Produit" },
  { value: "design", label: "Design" },
  { value: "sales", label: "Commercial" },
  { value: "marketing", label: "Marketing" },
  { value: "support", label: "Support client" },
  { value: "hr", label: "RH" },
  { value: "finance", label: "Finance" },
  { value: "ops", label: "Ops / Logistique" },
];

export interface CriteriaDraft {
  zone: Zone;
  locations: string[];
  remotePolicies: string[];
  languages: string[];
  jobFamilies: string[];
}

export const DEFAULT_CRITERIA: CriteriaDraft = {
  zone: "france",
  locations: [],
  remotePolicies: ["remote", "hybrid"],
  languages: ["fr", "en"],
  jobFamilies: [],
};

interface CriteriaStepProps {
  value: CriteriaDraft;
  onChange: (next: CriteriaDraft) => void;
  onSubmit: () => void;
  cityInput: string;
  setCityInput: (v: string) => void;
  /** L'email n'est demandé que si l'import du profil ne l'a pas livré. */
  needsEmail?: boolean;
  emailInput?: string;
  setEmailInput?: (v: string) => void;
  isSubmitting?: boolean;
  error?: string | null;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <p className="text-xs text-[#1A1918]/50 uppercase tracking-wider font-medium">
          {label}
        </p>
        {hint && <p className="text-[11px] text-[#1A1918]/45">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-3.5 py-1.5 rounded-full text-sm transition-all cursor-pointer border",
        active
          ? "border-[#006045] bg-[#006045]/8 text-[#006045] font-normal"
          : "border-[#1A1918]/12 text-[#1A1918]/55 hover:border-[#1A1918]/30 hover:text-[#1A1918]"
      )}
    >
      {children}
    </button>
  );
}

export function CriteriaStep({
  value,
  onChange,
  onSubmit,
  cityInput,
  setCityInput,
  needsEmail = false,
  emailInput = "",
  setEmailInput,
  isSubmitting = false,
  error = null,
}: CriteriaStepProps) {
  const toggle = (key: "remotePolicies" | "languages" | "jobFamilies", v: string) => {
    const list = value[key];
    onChange({
      ...value,
      [key]: list.includes(v) ? list.filter((x) => x !== v) : [...list, v],
    });
  };

  const addCity = (raw?: string) => {
    const city = (raw ?? cityInput).trim();
    if (!city || value.locations.includes(city)) {
      setCityInput("");
      return;
    }
    onChange({ ...value, locations: [...value.locations, city] });
    setCityInput("");
  };

  const removeCity = (city: string) =>
    onChange({ ...value, locations: value.locations.filter((c) => c !== city) });

  const suggestions = COMMON_CITIES.filter((c) => !value.locations.includes(c)).slice(0, 6);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="w-full space-y-7 text-left"
    >
      <Field label="Zone">
        <div className="flex flex-wrap gap-2">
          {ZONES.map((z) => (
            <Chip
              key={z.id}
              active={value.zone === z.id}
              onClick={() => onChange({ ...value, zone: z.id })}
            >
              {z.label}
            </Chip>
          ))}
        </div>
        <p className="text-[11px] text-[#1A1918]/45">
          {ZONES.find((z) => z.id === value.zone)?.hint}
        </p>
      </Field>

      <Field label="Villes" hint="facultatif">
        {value.locations.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {value.locations.map((city) => (
              <span
                key={city}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#006045]/8 text-[#006045] text-sm"
              >
                {city}
                <button
                  type="button"
                  onClick={() => removeCity(city)}
                  aria-label={`Retirer ${city}`}
                  className="text-[#006045]/50 hover:text-[#006045] cursor-pointer"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="relative">
          <MapPin className="absolute left-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#1A1918]/45 pointer-events-none" />
          <input
            type="text"
            value={cityInput}
            onChange={(e) => setCityInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCity();
              }
            }}
            placeholder="Ajouter une ville…"
            className="w-full pl-10 pr-11 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/50 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
          />
          {cityInput.trim() && (
            <button
              type="button"
              onClick={() => addCity()}
              aria-label="Ajouter la ville"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-[#006045] hover:bg-[#006045]/8 transition-colors cursor-pointer"
            >
              <Plus className="h-4 w-4" />
            </button>
          )}
        </div>

        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((city) => (
              <button
                key={city}
                type="button"
                onClick={() => addCity(city)}
                className="px-2.5 py-1 rounded-full text-xs text-[#1A1918]/55 hover:text-[#006045] transition-colors cursor-pointer"
              >
                + {city}
              </button>
            ))}
          </div>
        )}
      </Field>

      <Field label="Rythme">
        <div className="flex flex-wrap gap-2">
          {RHYTHMS.map((r) => (
            <Chip
              key={r.value}
              active={value.remotePolicies.includes(r.value)}
              onClick={() => toggle("remotePolicies", r.value)}
            >
              {r.label}
            </Chip>
          ))}
        </div>
      </Field>

      <Field label="Langues des annonces" hint="je n'enverrai rien dans une autre langue">
        <div className="flex flex-wrap gap-2">
          {LANGUAGES.map((l) => (
            <Chip
              key={l.value}
              active={value.languages.includes(l.value)}
              onClick={() => toggle("languages", l.value)}
            >
              {l.label}
            </Chip>
          ))}
        </div>
      </Field>

      <Field label="Métier" hint="laisse vide, je le déduis de ton CV">
        <div className="flex flex-wrap gap-2">
          {FAMILIES.map((f) => (
            <Chip
              key={f.value}
              active={value.jobFamilies.includes(f.value)}
              onClick={() => toggle("jobFamilies", f.value)}
            >
              {f.label}
            </Chip>
          ))}
        </div>
      </Field>

      {needsEmail && (
        <Field label="Ton email" hint="pour te tenir au courant">
          <input
            type="email"
            value={emailInput}
            onChange={(e) => setEmailInput?.(e.target.value)}
            placeholder="prenom@email.com"
            className="w-full px-3.5 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/50 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
          />
        </Field>
      )}

      {error && <p className="text-center text-xs text-red-600/80">{error}</p>}

      <div className="flex justify-center pt-1">
        <button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitting}
          className="group inline-flex items-center justify-center gap-2.5 py-4 px-8 text-[#006045] hover:text-[#000000] font-medium text-base transition-all cursor-pointer bg-transparent disabled:opacity-40"
        >
          <span>Oui, occupe-toi de tout</span>
          {isSubmitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          )}
        </button>
      </div>
    </motion.div>
  );
}
