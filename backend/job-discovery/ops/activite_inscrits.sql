-- Activité des inscrits — à lancer dans Supabase > SQL Editor (lecture seule).
-- Les valeurs d'énumérations sont comparées en texte minuscule (lower(...::text))
-- pour ne pas dépendre de la façon dont Postgres les stocke.

-- 1) Une ligne par inscrit des 30 derniers jours : jusqu'où il est allé.
with c as (
  select id, email, created_at,
         (resume_raw is not null or cv_content is not null) as a_un_cv,
         signature_image is not null as a_signe
  from candidates
  where created_at > now() - interval '30 days'
)
select
  c.created_at::date                                         as inscrit_le,
  c.email,
  c.a_un_cv,
  c.a_signe,
  (select count(*) from conversation_messages m join conversations cv on cv.id = m.conversation_id
     where cv.candidate_id = c.id and m.sender = 'user')     as messages_envoyes,
  (select count(*) from mission_runs r join missions mi on mi.id = r.mission_id
     where mi.candidate_id = c.id)                           as missions_lancees,
  (select count(*) from applications a where a.candidate_id = c.id)            as offres_retenues,
  (select count(*) from usage_events u where u.candidate_id = c.id and u.kind = 'pack') as dossiers_rediges,
  (select count(*) from application_dispatches d where d.candidate_id = c.id
     and lower(d.status::text) = 'sent')                     as candidatures_envoyees,
  (select count(*) from application_dispatches d where d.candidate_id = c.id
     and lower(d.status::text) = 'awaiting_approval')        as en_attente_de_validation,
  (select max(x) from (
     select max(m.created_at) x from conversation_messages m join conversations cv on cv.id = m.conversation_id where cv.candidate_id = c.id
     union all select max(u.created_at) from usage_events u where u.candidate_id = c.id
     union all select max(r.created_at) from mission_runs r join missions mi on mi.id = r.mission_id where mi.candidate_id = c.id
  ) t)                                                       as derniere_activite,
  exists (select 1 from subscriptions s where s.candidate_id = c.id) as a_un_abonnement
from c
order by c.created_at desc;

-- 2) L'entonnoir en chiffres (30 derniers jours).
with c as (select id from candidates where created_at > now() - interval '30 days')
select
  (select count(*) from c)                                                            as inscrits,
  (select count(*) from candidates k join c using (id) where k.resume_raw is not null or k.cv_content is not null) as avec_cv,
  (select count(distinct cv.candidate_id) from conversations cv join c on c.id = cv.candidate_id)             as ont_parle_a_alice,
  (select count(distinct mi.candidate_id) from mission_runs r join missions mi on mi.id = r.mission_id join c on c.id = mi.candidate_id) as ont_lance_une_mission,
  (select count(distinct u.candidate_id) from usage_events u join c on c.id = u.candidate_id where u.kind = 'pack') as ont_un_dossier,
  (select count(distinct d.candidate_id) from application_dispatches d join c on c.id = d.candidate_id where lower(d.status::text) = 'sent') as ont_envoye_une_candidature,
  (select count(distinct u.candidate_id) from (
     select candidate_id from usage_events where kind = 'pack' and created_at > now() - interval '7 days'
     group by candidate_id having count(*) >= 3) u join c on c.id = u.candidate_id)  as ont_atteint_la_limite_gratuite_7j,
  (select count(distinct s.candidate_id) from subscriptions s join c on c.id = s.candidate_id) as abonnes;
