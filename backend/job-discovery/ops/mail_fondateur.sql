-- Liste pour le mail du fondateur (lecture seule, Supabase > SQL Editor).
-- Niveaux : 1 candidatures envoyees, 2 a utilise Alice, 3 inscrit sans suite, 4 inscription inachevee.
-- Ajouter ses propres adresses de test dans la liste test ci-dessous.
-- Aucune apostrophe dans ces commentaires : elles cassent le decoupage de l editeur Supabase.
with test(motif) as (values
  ('%@ex.fr'), ('%@example.%'), ('%demo%@%'), ('%+test%@%')
),
c as (
  select k.*
  from candidates k
  where k.email is not null
    and not exists (select 1 from test where k.email ilike test.motif)
),
a as (
  select
    c.id,
    initcap(nullif(split_part(trim(coalesce(c.full_name, '')), ' ', 1), '')) as prenom,
    c.email,
    c.created_at::date                                                   as inscrit_le,
    c.last_seen_at::date                                                 as derniere_visite,
    (c.resume_raw is not null or c.cv_content is not null)               as a_un_cv,
    (select count(*) from conversation_messages m
       join conversations cv on cv.id = m.conversation_id
      where cv.candidate_id = c.id and m.sender = 'user')                as messages,
    (select count(*) from mission_runs r
       join missions mi on mi.id = r.mission_id
      where mi.candidate_id = c.id)                                      as missions,
    (select count(*) from usage_events u
      where u.candidate_id = c.id and u.kind = 'pack')                   as dossiers,
    (select count(*) from application_dispatches d
      where d.candidate_id = c.id and lower(d.status::text) = 'sent')    as envoyees,
    (select count(*) from application_dispatches d
      where d.candidate_id = c.id
        and lower(d.status::text) in ('awaiting_approval', 'prepared'))  as en_attente,
    (select count(*) from applications ap
      where ap.candidate_id = c.id
        and lower(ap.status::text) in ('interview', 'offer'))           as reponses,
    exists (select 1 from subscriptions s where s.candidate_id = c.id)   as abonne,
    coalesce(c.notification_prefs ->> 'reengagement', 'true') = 'false'  as refuse_les_relances
  from c
)
select
  case
    when envoyees > 0                                  then '1 · candidatures envoyées'
    when missions > 0 or dossiers > 0 or messages > 0  then '2 · a utilisé Alice'
    when a_un_cv                                       then '3 · inscrit sans suite'
    else                                                    '4 · inscription inachevée'
  end                                                  as niveau,
  prenom,
  email,
  inscrit_le,
  derniere_visite,
  messages, missions, dossiers, envoyees, en_attente, reponses,
  abonne,
  refuse_les_relances,
  case
    when envoyees > 0 then
      'P.S. : Alice a déjà envoyé ' || envoyees || ' candidature' || case when envoyees > 1 then 's' else '' end
      || ' pour toi. Tu as eu des retours ?'
    when en_attente > 0 then
      'P.S. : ' || en_attente || ' dossier' || case when en_attente > 1 then 's sont prêts' else ' est prêt' end
      || ' et t''attend' || case when en_attente > 1 then 'ent' else '' end || ' dans ton espace.'
    when missions > 0 or dossiers > 0 or messages > 0 then
      'P.S. : qu''est-ce qui t''a arrêté(e) en route ? Ta réponse m''aide énormément.'
    when a_un_cv then
      'P.S. : ton CV est déjà là, il suffit de dire à Alice ce que tu cherches.'
    else
      'P.S. : il ne manque que ton CV pour qu''Alice se mette au travail.'
  end                                                  as ps_suggere
from a
order by niveau, inscrit_le desc;
