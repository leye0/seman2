# Schémas canoniques des sources conversationnelles

Les sources téléchargées restent immuables. Les tables ci-dessous sont des représentations de travail reproductibles sous `data/parquet/<dataset>/schema_version=1/`.

## Conventions communes

- texte Unicode et retours à la ligne conservés sans réécriture ;
- identifiants natifs privilégiés ;
- identifiants dérivés explicitement signalés ;
- `native_vote_score` signé et nullable, sans interprétation comme vérité ou qualité objective ;
- provenance par `source_file`, `source_position` et `source_record_id` ;
- absence d'information représentée par `null`, jamais inventée.

## Reddit

### `submissions`

```text
submission_id string
subreddit string
author_name string
author_state string
created_at timestamp
created_utc int64
title string
body string
url string
native_vote_score int64
is_edited bool nullable
edited_at timestamp nullable
moderation_state string
num_comments int64
over_18 bool
link_flair_text string nullable
author_flair_text string nullable
source_file string
source_position int64
source_record_id string
```

### `comments`

```text
comment_id string
submission_id string
parent_id string
parent_kind string        # submission | comment | unknown
author_name string
author_state string
created_at timestamp
created_utc int64
body string
native_vote_score int64
is_edited bool nullable
edited_at timestamp nullable
moderation_state string
distinguished string nullable
author_flair_text string nullable
raw_link_id string
raw_parent_id string
source_file string
source_position int64
source_record_id string
```

Les préfixes Reddit natifs sont normalisés de manière déterministe : `t3_` désigne une publication et `t1_` un commentaire. La tranche de mai 2018 peut contenir des nœuds de frontière dont la racine ou le parent se trouve hors du mois ; cette propriété doit être validée séparément.

## Stack Overflow

La source locale est déjà un dérivé du dump Stack Exchange : elle regroupe une question et des listes de réponses, mais ne conserve pas les identifiants, auteurs, dates ni statut d'acceptation des réponses.

### `questions`

```text
question_id string
title string
body string
tags list<string>
native_vote_score int64 nullable
accepted_answer_id string nullable
created_at timestamp nullable
answer_count int64
source_file string
source_position int64
source_record_id string
```

### `answers`

```text
answer_id string             # identifiant dérivé
answer_id_is_native bool     # toujours false pour cette source
question_id string
body string
native_vote_score int64
is_accepted bool nullable
author_name string nullable
created_at timestamp nullable
source_group string          # valeur source: answers | non_answers
source_ordinal int32
source_file string
source_position int64
source_record_id string
```

`answer_id` est construit de façon stable avec `question_id`, `source_group` et `source_ordinal`. `source_group` conserve strictement la distinction fournie par le dataset ; elle n'est pas interprétée comme un statut d'acceptation ou de correction.
