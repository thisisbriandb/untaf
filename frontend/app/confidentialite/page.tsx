import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Confidentialité · Alice",
  description:
    "Quelles données Alice et son extension utilisent, pourquoi, avec qui elles sont partagées, et comment les supprimer.",
};

const UPDATED = "13 octobre 2026";
const CONTACT = "briand@alice-agent.fr";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-[20px] font-semibold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-[#1A1918]/75">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <main className="min-h-[100dvh] bg-[#FAFAF8] px-4 py-12 text-[#1A1918] sm:px-6 sm:py-16">
      <article className="mx-auto max-w-2xl">
        <Link href="/" className="text-[13px] text-[#6B6B68] hover:text-[#006045]">
          ← Alice
        </Link>
        <h1 className="mt-6 text-[32px] font-semibold leading-tight tracking-tight sm:text-[40px]">
          Confidentialité
        </h1>
        <p className="mt-3 text-[14px] text-[#6B6B68]">Mise à jour le {UPDATED}</p>
        <p className="mt-6 text-[15px] leading-relaxed text-[#1A1918]/75">
          Alice (alice-agent.fr) est un assistant de recherche d&apos;emploi : il trouve des offres, adapte ton CV
          et ta lettre à chacune, et t&apos;aide à postuler. Cette page explique quelles données Alice et son
          extension pour navigateur utilisent, pourquoi, et comment tu gardes la main dessus.
        </p>

        <Section title="Qui est responsable">
          <p>
            Alice est éditée par Briand Bataillon. Pour toute question sur tes données, ou pour exercer tes
            droits : <a className="text-[#006045] underline" href={`mailto:${CONTACT}`}>{CONTACT}</a>.
          </p>
        </Section>

        <Section title="Les données que tu nous confies">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Ton compte</strong> : adresse e-mail (connexion par lien ou code envoyé par e-mail).
            </li>
            <li>
              <strong>Ton parcours</strong> : CV, nom, téléphone, ville, expériences, formations, compétences,
              liens (LinkedIn, portfolio), photo et signature si tu les ajoutes.
            </li>
            <li>
              <strong>Ta recherche</strong> : critères (métier, ville, type de contrat), conversations avec Alice,
              offres retenues, CV et lettres adaptés, candidatures envoyées et leur suivi.
            </li>
            <li>
              <strong>Les réponses des recruteurs</strong> reçues sur l&apos;adresse de suivi d&apos;Alice, pour
              les afficher dans ton espace.
            </li>
            <li>
              <strong>Ton abonnement</strong>, si tu en prends un : le paiement est traité par Lemon Squeezy ;
              Alice ne voit ni ne stocke ta carte bancaire.
            </li>
          </ul>
          <p>Elles servent uniquement à faire fonctionner Alice pour toi : chercher, préparer et envoyer tes candidatures, et t&apos;en tenir informé.</p>
        </Section>

        <Section title="L'extension pour navigateur">
          <p>
            L&apos;extension « Alice — candidatures en un clic » agit dans ton navigateur, avec ta propre session
            sur les sites d&apos;emploi.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Tes identifiants ne quittent jamais ton ordinateur.</strong> L&apos;extension ne lit pas, ne
              stocke pas et n&apos;envoie jamais tes mots de passe ni tes identifiants des sites d&apos;emploi.
            </li>
            <li>
              Sur chaque page, elle vérifie <strong>localement</strong>, dans ton navigateur, si la page
              ressemble à une offre d&apos;emploi ou à un formulaire de candidature. Sur toute autre page, elle
              n&apos;affiche rien et <strong>n&apos;envoie rien</strong>.
            </li>
            <li>
              Sur une page d&apos;offre, si tu es connecté à Alice, l&apos;adresse de la page est envoyée à Alice
              pour savoir si cette offre est déjà dans ta liste.
            </li>
            <li>
              Quand <strong>tu cliques</strong> sur « Ajouter à Alice », le texte de l&apos;annonce est envoyé pour
              l&apos;ajouter à ta liste. Quand tu cliques sur « Remplir avec Alice », les intitulés des champs du
              formulaire sont envoyés pour préparer les réponses, et l&apos;extension remplit le formulaire avec
              ton parcours, ton CV adapté et ta lettre.
            </li>
            <li>
              <strong>Rien n&apos;est envoyé au recruteur sans ton clic</strong> sur le bouton « Envoyer » du
              site. Les champs sensibles (consentements, conditions, handicap, genre, origine…) ne sont jamais
              remplis.
            </li>
            <li>
              L&apos;extension garde dans le stockage de ton navigateur ta session Alice (pour ne pas te
              redemander de te connecter) et, temporairement, le CV adapté à l&apos;offre en cours.
            </li>
          </ul>
        </Section>

        <Section title="Avec qui elles sont partagées">
          <p>Tes données ne sont jamais vendues ni utilisées pour de la publicité. Elles passent uniquement par les prestataires nécessaires au service :</p>
          <ul className="list-disc space-y-2 pl-5">
            <li><strong>Les recruteurs</strong> à qui tu postules : CV, lettre et coordonnées de la candidature concernée.</li>
            <li><strong>Supabase</strong> (base de données), <strong>Railway</strong> (serveur d&apos;Alice), <strong>Vercel</strong> (site).</li>
            <li><strong>Google (Gemini)</strong> : rédaction et adaptation des CV, lettres et réponses aux questions des formulaires.</li>
            <li><strong>Resend</strong> : envoi des e-mails (connexion, candidatures, notifications).</li>
            <li><strong>Lemon Squeezy</strong> : paiement des abonnements.</li>
          </ul>
        </Section>

        <Section title="Combien de temps">
          <p>
            Tes données sont conservées tant que ton compte existe. Tu peux demander à tout moment leur
            suppression complète en écrivant à{" "}
            <a className="text-[#006045] underline" href={`mailto:${CONTACT}`}>{CONTACT}</a> : elle est faite sous
            30 jours. Désinstaller l&apos;extension efface ce qu&apos;elle gardait dans ton navigateur.
          </p>
        </Section>

        <Section title="Tes droits">
          <p>
            Conformément au RGPD, tu peux accéder à tes données, les corriger, les exporter, t&apos;opposer à un
            traitement ou demander leur suppression, en écrivant à{" "}
            <a className="text-[#006045] underline" href={`mailto:${CONTACT}`}>{CONTACT}</a>. Tu peux aussi adresser
            une réclamation à la CNIL (cnil.fr). Les e-mails de relance d&apos;Alice se coupent depuis tes
            paramètres ou le lien présent dans chaque e-mail.
          </p>
        </Section>
      </article>
    </main>
  );
}
