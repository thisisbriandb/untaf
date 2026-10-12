import type { Metadata } from "next";
import { API_BASE_URL } from "@/lib/config";
import type { CommunityList } from "@/lib/community";
import { CommunityBoard } from "./CommunityBoard";

// La liste est régénérée au plus toutes les 15 minutes : page statique pour
// les visiteurs et les moteurs de recherche, à jour sans redéploiement.
export const revalidate = 900;

export const metadata: Metadata = {
  title: "Alternances et stages 2027 en France · Alice Community",
  description:
    "Toutes les offres d'alternance et de stage en France, mises à jour chaque jour. " +
    "Filtre par métier et par ville, et postule avec Alice : CV et lettre adaptés à chaque offre.",
  openGraph: {
    title: "Alternances et stages 2027 · Alice Community",
    description: "Les offres d'alternance et de stage en France, mises à jour chaque jour.",
    type: "website",
  },
};

async function loadOffers(): Promise<CommunityList | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/community/offres`, { next: { revalidate: 900 } });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function CommunityPage() {
  const data = await loadOffers();
  return <CommunityBoard data={data} />;
}
