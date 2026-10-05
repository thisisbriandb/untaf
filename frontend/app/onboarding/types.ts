export interface ColorSwatch {
  id: string;
  name: string;
  bg: string;
  border: string;
  text: string;
  hex: string;
}

export interface CVTemplate {
  id: string;
  name: string;
  tagline: string;
  badge: string;
  layout: string;
  photo: string;
  fictionalName: string;
  fictionalRole: string;
  location: string;
  email: string;
  summary: string;
  skills: string[];
  description: string;
}

export interface CVAuditData {
  ats_score: number;
  score_label: string;
  strengths: string[];
  improvements: string[];
  optimized_headline: string;
  optimized_summary: string;
  suggested_skills: string[];
}

export interface OptionItem {
  label: string;
  value: string;
}

// ─── CV Editor Data Models ──────────────────────────────────────────────────

export interface ExperienceEntry {
  id: string;
  jobTitle: string;
  company: string;
  location: string;
  startDate: string;   // "2022-01" format
  endDate: string;      // "2025-07" or "present"
  isCurrent: boolean;
  highlights: string[];
}

export interface EducationEntry {
  id: string;
  degree: string;
  institution: string;
  location: string;
  startYear: string;
  endYear: string;
  description: string;
}

export interface LanguageEntry {
  id: string;
  language: string;
  level: string;
}

export type CvEditorSubStep = "personal" | "experiences" | "education" | "skills" | "languages";

export interface CvEditorSubStepConfig {
  id: CvEditorSubStep;
  label: string;
  shortLabel: string;
}

export const cvEditorSubSteps: CvEditorSubStepConfig[] = [
  { id: "personal", label: "Informations personnelles", shortLabel: "Infos" },
  { id: "experiences", label: "Expériences professionnelles", shortLabel: "Exp." },
  { id: "education", label: "Formation", shortLabel: "Études" },
  { id: "skills", label: "Compétences", shortLabel: "Skills" },
  { id: "languages", label: "Langues", shortLabel: "Langues" },
];

export const languageLevels = [
  "Langue maternelle",
  "Courant (C1-C2)",
  "Professionnel (B2)",
  "Intermédiaire (B1)",
  "Élémentaire (A2)",
  "Débutant (A1)",
];

// ─── Existing Constants ─────────────────────────────────────────────────────

export const colorSwatches: ColorSwatch[] = [
  { id: "navy", name: "Bleu Steel Untaf", bg: "bg-[#234C6A]", border: "border-[#234C6A]", text: "text-[#234C6A]", hex: "#234C6A" },
  { id: "darknavy", name: "Bleu Nuit Untaf", bg: "bg-[#1B3C53]", border: "border-[#1B3C53]", text: "text-[#1B3C53]", hex: "#1B3C53" },
  { id: "slate", name: "Ardoise Slate", bg: "bg-[#456882]", border: "border-[#456882]", text: "text-[#456882]", hex: "#456882" },
  { id: "sand", name: "Sable Warm", bg: "bg-[#D2C1B6]", border: "border-[#D2C1B6]", text: "text-[#D2C1B6]", hex: "#D2C1B6" },
  { id: "emerald", name: "Émeraude", bg: "bg-[#161615]", border: "border-[#161615]", text: "text-[#161615]", hex: "#059669" },
  { id: "violet", name: "Violet Studio", bg: "bg-[#161615]", border: "border-[#161615]", text: "text-[#161615]", hex: "#7c3aed" },
];

export const cvTemplates: CVTemplate[] = [
  {
    id: "minimalist",
    name: "Modèle Épuré",
    tagline: "Lisibilité ATS 100%",
    badge: "1-Colonne",
    layout: "1-col",
    photo: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&auto=format&fit=crop&q=80",
    fictionalName: "MARIE BERNARD",
    fictionalRole: "INGÉNIEURE LOGICIEL SENIOR",
    location: "Paris, France",
    email: "marie.bernard@email.fr",
    summary: "Ingénieure logiciel avec 5 ans d'expérience en conception d'architectures SaaS et APIs Python/TypeScript.",
    skills: ["TypeScript", "React", "Node.js", "Python", "Docker"],
    description: "Structure épurée sur 1 colonne. Idéal pour une lecture fluide et directe."
  },
  {
    id: "tech",
    name: "Moderne 2-Colonnes",
    tagline: "Sidebar Compétences",
    badge: "Populaire Tech",
    layout: "left-sidebar",
    photo: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&auto=format&fit=crop&q=80",
    fictionalName: "ALEXANDRE DUBOIS",
    fictionalRole: "DÉVELOPPEUR FULL STACK",
    location: "Lyon, France",
    email: "a.dubois@tech.io",
    summary: "Développeur passionné par les technologies du Web moderne et les architectures Cloud Native.",
    skills: ["Next.js", "GraphQL", "PostgreSQL", "Kubernetes", "AWS"],
    description: "Panneau latéral dédié aux compétences techniques et projets."
  },
  {
    id: "executive",
    name: "Bandeau Executive",
    tagline: "Sobriété Institutionnelle",
    badge: "Executive",
    layout: "top-header",
    photo: "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=200&auto=format&fit=crop&q=80",
    fictionalName: "CLAIRE MARTIN",
    fictionalRole: "DIRECTRICE DE PROJETS IT",
    location: "Paris, France",
    email: "c.martin@exec.com",
    summary: "Direction de projets d'envergure, conduite du changement et encadrement d'équipes.",
    skills: ["Management", "Agile/Scrum", "Stratégie IT", "Budget & KPIs"],
    description: "Bandeau d'en-tête supérieur avec mise en valeur des responsabilités."
  },
  {
    id: "creative",
    name: "Studio Créatif",
    tagline: "Design & Impact",
    badge: "Créatif",
    layout: "creative",
    photo: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=200&auto=format&fit=crop&q=80",
    fictionalName: "LUCAS MOREAU",
    fictionalRole: "PRODUCT DESIGNER & UX",
    location: "Bordeaux, France",
    email: "lucas@studio.design",
    summary: "Concepteur d'interfaces utilisateur centrées sur l'expérience et l'ergonomie.",
    skills: ["Figma", "UI/UX", "Design System", "Prototypage", "User Research"],
    description: "Mise en page visuelle équilibrée avec pastilles de couleurs."
  },
  {
    id: "classic",
    name: "Classic Encadré",
    tagline: "Lignes Sobres",
    badge: "Standard",
    layout: "classic",
    photo: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&auto=format&fit=crop&q=80",
    fictionalName: "THOMAS BENOIT",
    fictionalRole: "CONSULTANT SENIOR SI",
    location: "Nantes, France",
    email: "t.benoit@consulting.fr",
    summary: "Accompagnement stratégique des entreprises dans la modernisation de leur système d'information.",
    skills: ["Conseil Strategy", "Analyse Métier", "Audit SI", "Governance"],
    description: "Présentation sobre et intemporelle avec lignes de séparation fines."
  },
  {
    id: "compact",
    name: "Compact Professionnel",
    tagline: "Haute Densité",
    badge: "Compact",
    layout: "compact",
    photo: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&auto=format&fit=crop&q=80",
    fictionalName: "SOPHIE LEROY",
    fictionalRole: "DEVOPS & CLOUD ARCHITECT",
    location: "Toulouse, France",
    email: "sophie.leroy@cloud.net",
    summary: "Experte en automatisation CI/CD, conteneurisation et sécurité des infrastructures Cloud.",
    skills: ["Terraform", "Ansible", "CI/CD", "Docker", "Linux Admin"],
    description: "Densité d'information optimisée pour faire tenir toutes vos expériences sur une seule page."
  }
];

export const contractOptions: OptionItem[] = [
  { label: "CDI", value: "cdi" },
  { label: "CDD", value: "cdd" },
  { label: "Freelance", value: "freelance" },
  { label: "Alternance", value: "alternance" }
];

export const remoteOptions: OptionItem[] = [
  { label: "Télétravail", value: "remote" },
  { label: "Hybride", value: "hybrid" },
  { label: "Sur site", value: "onsite" }
];
