import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { API_BASE_URL } from "@/lib/config";

const geist = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Alice — Votre Agent de Carrière IA",
  description: "La recherche d'emploi ne doit pas devenir un emploi. Laissez Alice trouver et candidater pour vous.",
  // L'extension navigateur lit cette adresse pour appeler la même API que le site.
  other: { "alice-api": API_BASE_URL },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="fr"
      className={`${geist.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body
        suppressHydrationWarning
        className="flex min-h-full flex-col bg-[#FAFAF8] text-[#1A1918] font-sans selection:bg-[#006045]/15 selection:text-[#006045]"
      >
        {children}
      </body>
    </html>
  );
}
