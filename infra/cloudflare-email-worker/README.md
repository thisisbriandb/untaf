# Réception des réponses des recruteurs (Cloudflare, gratuit)

Les recruteurs répondent à l'adresse de candidature du candidat
(`prenom.nom.xxxxx@reponses.alice-agent.fr`). Cloudflare Email Routing reçoit
ces e-mails et ce Worker les transmet à l'API d'Alice
(`POST /api/inbound/email`), qui les lit, met le suivi à jour et les transfère
au candidat.

## Mise en place

Prérequis : les DNS de `alice-agent.fr` sont gérés par Cloudflare.

1. **Railway** : renseigner `INBOUND_SECRET` (une longue chaîne aléatoire,
   ex. `openssl rand -hex 32`). Ne pas encore renseigner `INBOUND_DOMAIN`.
2. **Cloudflare → Email → Email Routing** : activer le routage pour le
   sous-domaine `reponses.alice-agent.fr` (Cloudflare ajoute les MX et le SPF).
3. **Workers → Créer** un Worker, coller `worker.js`, puis dans ses
   variables :
   - `ALICE_INBOUND_URL` = `https://<api>/api/inbound/email`
   - `INBOUND_SECRET` = la même valeur que sur Railway (type « Secret »)
   - `FALLBACK_TO` (conseillé) = une adresse à toi, vérifiée dans Email
     Routing → Destination addresses : elle reçoit l'e-mail si l'API ne
     répond pas.
4. **Email Routing → Routing rules → Catch-all** du sous-domaine :
   action « Send to a Worker », ce Worker.
5. **Tester** : écrire à `test@reponses.alice-agent.fr`. Les journaux du
   Worker doivent montrer un envoi réussi (l'API répond 204 ; l'adresse
   n'étant à personne, l'e-mail est ignoré, c'est normal).
6. **Activer** : sur Railway, `INBOUND_DOMAIN=reponses.alice-agent.fr`. À
   partir de là, les candidatures donnent l'adresse de candidature. Écrire à
   l'adresse affichée dans Alice (onglet Messages) pour vérifier qu'elle
   arrive bien dans la boîte et dans ta messagerie.

Avec Wrangler plutôt que le tableau de bord : `wrangler deploy` dans ce
dossier (voir `wrangler.toml`), puis `wrangler secret put INBOUND_SECRET`.
