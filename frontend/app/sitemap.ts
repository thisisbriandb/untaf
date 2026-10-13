import type { MetadataRoute } from "next";

const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "https://alice-agent.fr").replace(/\/+$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: SITE, changeFrequency: "weekly", priority: 1 },
    // Alice Community : la liste change chaque jour.
    { url: `${SITE}/communaute`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE}/confidentialite`, changeFrequency: "yearly", priority: 0.2 },
  ];
}
