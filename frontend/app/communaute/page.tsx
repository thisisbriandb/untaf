import type { Metadata } from "next";
import { DEFAULT_FILTERS, searchUrl, type CommunityPage } from "@/lib/community";
import { CommunityBoard } from "./CommunityBoard";

// La liste est régénérée au plus toutes les 15 minutes : page statique pour
// les visiteurs et les moteurs de recherche, à jour sans redéploiement.
export const revalidate = 900;

export const metadata: Metadata = {
  title: "Alternances, stages et premiers emplois en France · Alice Community",
  description:
    "Les offres d'alternance, de stage et de premier emploi en France, mises à jour chaque jour. " +
    "Filtre par métier et par ville, et postule avec Alice : CV et lettre adaptés à chaque offre.",
  openGraph: {
    title: "Alternances, stages et premiers emplois · Alice Community",
    description: "Les offres d'alternance, de stage et de premier emploi en France, mises à jour chaque jour.",
    type: "website",
  },
};

async function loadOffers(): Promise<CommunityPage | null> {
  // Première page des alternances, rendue côté serveur (moteurs de recherche) ;
  // les filtres et les pages suivantes sont demandés par le navigateur.
  const url = searchUrl(DEFAULT_FILTERS);
  try {
    const res = await fetch(url, { next: { revalidate: 900 } });
    if (res.ok) return await res.json();
    // Visible dans les journaux de l'hébergeur : sans cela, la page restait
    // vide sans que rien ne dise pourquoi.
    console.error(`Alice Community : ${url} a répondu ${res.status}`);
  } catch (err) {
    console.error(`Alice Community : ${url} injoignable`, err);
  }
  return null;
}

export default async function CommunityPage() {
  const data = await loadOffers();
  return <CommunityBoard initial={data} />;
}
