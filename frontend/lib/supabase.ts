/**
 * Client Supabase Auth du navigateur.
 *
 * Sans NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY, l'application
 * tourne sans authentification (développement local, avec AUTH_DISABLED=true
 * côté API). La clé « anon » est publique par construction : elle ne donne
 * accès à rien tant que le RLS est actif sur les tables.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const AUTH_ENABLED = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = AUTH_ENABLED
  ? createClient(url!, anonKey!, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

/** Jeton d'accès courant, rafraîchi au besoin par le client. */
export async function accessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function signOut(): Promise<void> {
  await supabase?.auth.signOut();
}
