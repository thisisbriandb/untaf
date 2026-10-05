import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

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
        className="flex min-h-full flex-col bg-[#FAFAF8] text-[#1A1918] font-sans selection:bg-[#161615]/15 selection:text-[#161615]"
      >
        {children}
      </body>
    </html>
  );
}
