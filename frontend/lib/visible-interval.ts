/**
 * Un rafraîchissement périodique qui s'arrête quand l'onglet est caché, et
 * reprend (aussitôt) quand on y revient. Un onglet oublié ouvert toute la
 * journée ne doit pas interroger le serveur toutes les quelques secondes.
 */
export function everyWhileVisible(fn: () => void, ms: number): () => void {
  let timer: ReturnType<typeof setInterval> | null = null;
  const start = () => {
    if (timer === null) timer = setInterval(fn, ms);
  };
  const stop = () => {
    if (timer !== null) clearInterval(timer);
    timer = null;
  };
  const onVisibility = () => {
    if (document.hidden) {
      stop();
    } else {
      fn();
      start();
    }
  };
  if (!document.hidden) start();
  document.addEventListener("visibilitychange", onVisibility);
  return () => {
    stop();
    document.removeEventListener("visibilitychange", onVisibility);
  };
}
