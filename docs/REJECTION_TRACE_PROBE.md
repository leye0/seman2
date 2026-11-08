# Instrumenting unification rejection without declaring grammar errors

The public parse gateway offers an **opt-in**, bounded
`rejection_trace_limit` in the range 0–100. Default 0 is an unchanged
fast path; debug requests bypass the parse cache and are **not**
canonical 500-case measurements.

`stats.rejection_trace` and, when a failed scoped dialogue was attempted,
`stats.dialogue_attempt.rejection_trace` provide a sample of attempted
derivations rejected in the lazy k-best materializer.

- `lexical_unification` and `rule_lhs_unification`: actual unifier
  returned no result at the lexical or rule interface.
- `lexical_hint_unification` and `rule_hint_unification`: a constrained
  k-best bound was incompatible, **not** an executed full derivation.
- `child_context_exhausted`: a particular constrained child stream was
  actually exhausted; this is **not** an observed direct feature mismatch.
- `interface_unification`: segmented interface candidate rejected.

Each event retains the requested/category span, `rule_id` if available,
the requested/offered raw feature structures, and any directly
contradictory **atomic** feature pair after bound substitution. Those
atoms prove incompatibility **of that one attempted pair only**.
Open-world missing values, unbound variables, disjunctions, lexical
ambiguities and structural constraints must not be reinterpreted as
a grammatical fault. Sampling is per-stage and globally bounded;
`observed_events` can exceed the number of retained samples.

Research workflow: after the unchanged single-pass fixed 500-case
evaluation and its source-context triage, the separate
`scripts.probe_dialogue_rejections` replay selects canonical failures
where `dialogue_attempt.structural_root_nodes > 0`. It checks that
all 500 source records and the pinned cohort checksum align, and
replays only the selected dialogue cases through
`parse_corpus_case` and `Parser.parse` using their original
quote-balanced analysis text, the same 50,000/500,000 budgets, and
an independent 10-second wall deadline.

Output in the workflow artifact:
`dialogue_rejection_probes.jsonl`,
`dialogue_rejection_summary.json`,
`dialogue_rejection_report.md`. An independent replay may time out or
differ from the canonical pass; it never changes the original status.
No complete parse tree is fabricated, and no possible grammatical
violation is inferred from a failed parse alone.

This is the **first research instrument**, not yet a complete causal
explainer or a proof-licensed local anomaly detector.

## Source coordinates

The independent replay report retains original `analysis_span` coordinates,
then maps `reference_span` (and child spans) with
`PreparedCorpusInput.reference_span`. Mapping is `exact` only for
characters in the original frozen case; synthetic quotation delimiters
or unavailable regions are `null` with `reference_span_mapping=unavailable`.
No offset is inferred from token order or from source neighbors.

## Second tranche : exigences de preuve positive et ascendance des requêtes

L'instrument observe désormais les branches rejetées parce qu'un trait
`requires` **n'est pas positivement établi**, ce qui est distinct
d'une incompatibilité de valeur atomique :

- `positive_evidence_lexical_hint_missing` : lecture lexicale intrinsèque
  dépourvue d'un trait requis dans un calcul de borne k-best
- `positive_evidence_interface_missing` : interface segmentée sans preuve
  intrinsèque requise
- `positive_evidence_rule_hint_impossible` et
  `positive_evidence_rule_impossible` : règle incapable de fournir
  statiquement la preuve demandée (test conservateur
  `_rule_may_provide_evidence`)
- `positive_evidence_materialized_missing` : une analyse
  effectivement matérialisée ne porte pas toute la preuve exigée,
  même si ses traits sont par ailleurs unifiables

Une trace inclut `required_positive_features`,
`witnessed_positive_features` et `missing_positive_features`
**seulement** lorsque les traits observés sont réellement disponibles.
Le rejet d'une règle statiquement incapable de fournir la preuve
ne signifie pas que toutes les autres règles sont incapables de la
fournir.

`request_chain` expose jusqu'à **six** contextes de calcul imbriqués
avec catégorie, span, `via_rule_id` et `via_child_index`, ainsi que
`request_chain_truncated`. Ce sont des demandes de constituants
lors d'une même recherche — **pas** une chaîne d'échecs nécessaire
et suffisante ni l'assurance que tous les ancêtres échouent.
Les spans du chaînage suivent les mêmes règles de correspondance
exacte à la source ; les guillemets transférés demeurent non mappés.

Deux contrôles stricts déjà complets (**76, 244**) et les deux cas
à analyse marquée prouvée par tests indépendants (**463, 480**) sont
rejoués séparément avec le même texte préparé et les mêmes
budgets que l'analyse canonique. Des résultats
`deadline_censored` restent possibles sous instrumentation.
Les rapports supplémentaires
`dialogue_rejection_comparators.jsonl` et
`dialogue_rejection_comparators.md` ne remplacent jamais
les mesures de référence.

**Limite non levée :** cette instrumentation n'est pas un moteur
de démonstration de causalité globale. Il faut ensuite explorer les
derivations concurrentes, l'absence de preuve dans *toutes*
les solutions, les rapports positifs de contrôles et les tronquages
de recherche avant de conclure à une anomalie de phrase.

## Échantillonnage priorisé (sans changer l'exécution)

Le rapport conserve toujours les compteurs `observed_by_stage` de
toutes les tentatives observées sous instrumentation. La limite globale
sur `events` et une limite par type empêchent de déborder la mémoire.

Si des incompatibilités de bornes k-best ont déjà rempli la fenêtre,
un événement ultérieur **plus directement établi** peut remplacer un
échantillon de priorité inférieure, de manière déterministe :

1. Flux d'enfant contextuel réellement épuisé.
2. Analyse matérialisée dépourvue d'une preuve `requires`.
3. Rejet d'unification réellement tenté et preuve statiquement
   impossible dans une règle.
4. Preuve non fournie dans l'estimation des bornes.
5. Incompatibilités ordinaires des bornes k-best.

La sortie expose
`sampling_policy=per_stage_cap_with_priority_replacement`. Il s'agit
d'un **échantillon non chronologique et non exhaustif** ; les
compteurs d'origine sont conservés mais les événements retenus ne
doivent pas servir à estimer une fréquence statistique ou une cause
grammaticale. Les décisions du parseur, les budgets et l'arbre
sélectionné ne dépendent jamais de ce choix d'observations.

## P2 : preuves positives de sous-arbres réellement matérialisés

Lorsque `rejection_trace_limit` est activé, un second échantillonneur
borné collecte des **règles locales dont la composition a réussi**.
Le point d'observation se trouve *après* l'unification des traits avec
le contexte demandé, l'obtention des analyses enfants et la vérification
positive de `requires`, lors de l'ajout effectif à `state.results`.

La clé `validated_local_constituents` du même objet de trace conserve :

- `category`, `rule_id`, `analysis_span`, traits vérifiés et contraintes du
  contexte dans lequel l'analyse a été validée;
- enfants ordonnés avec leurs catégories, règles et spans distincts;
- compteurs `observed_materialized_rule_analyses` et
  `sampled_local_constituents`, avec priorité aux plus grands spans et
  maximum deux variantes d'un même couple catégorie/span;
- les preuves positives présentes, ainsi que les limites
  `exhaustive=false`, `global_tree_proven=false` et
  `sentence_grammatical_fault_established=false`.

Ce sont de **véritables compositions localement unifiées**, mais sous
des contraintes propres à une tentative. Elles ne démontrent ni le bon
rattachement à la matrice, ni l'existence d'un arbre global, ni une faute.
Les lectures lexicales isolées et les simples nœuds structurels ne sont
pas présentés comme des preuves de constituants.

Le rejeu de dialogue transfère les spans des sous-arbres et **de chacun
de leurs enfants** vers la référence source seulement lorsque le mapping
est exact. La synthèse des 26 cas garde ces preuves séparées des rejets.

**Constat de contrôle :** sur l'Action 42421159717, les **103** preuves
de cette première forme provenaient toutes des deux comparateurs *marqués
déjà complets* (#463 et #480). Les relectures de dialogue incomplètes
n'ont fourni aucune preuve positive par ce seul mécanisme. Il serait
incorrect de compter ces 103 éléments comme preuves obtenues *malgré*
l'échec d'une racine globale.

## P2 : sondage indépendant de constituants après racine introuvable

Si le rejeu opt-in a fini d'explorer la racine, sans analyse complète
et **sans saturation de la forêt**, la même forêt reconnue est sondée
avec un **nouveau** matérialiseur à contexte local libre. Il n'ajoute
aucune règle et ne change ni la racine choisie, ni l'ordre des analyses,
ni `kbest_work_units`, ni les budgets canoniques : il possède son propre
plafond de **12 000 unités de travail**.

Le sondage sélectionne au maximum 48 nœuds structurels contenant des
règles, de catégories NP/PP/ADJP/VP/SPEECH-TAG/CLAUSE, avec des spans
non triviaux. Quatre petits et quatre grands spans par catégorie sont
alternés. Chaque règle publiée sous `independent_local_probe.witnesses`
doit avoir effectivement réussi l'unification de ses enfants et traits,
et son mapping source (y compris celui de ses enfants) demeure exact ou
explicitement indisponible. On publie également nombre de nœuds
essayés/acceptés, travail séparé consommé et éventuelle saturation
du sondage. `validated_local_constituents` reste la preuve recueillie
pendant l'essai normal de racine : les deux provenances ne sont jamais
mélangées dans la synthèse des 26 cas.

**Résultat mesuré sur l'Action
[42422126032](https://github.com/leye0/seman2/actions/runs/42422126032)** :
les sept relectures de dialogue incomplètes ont maintenant **521**
témoins indépendants, dont **510** avec une correspondance exacte
de tous les spans source/descendants. Les sept cas ont des preuves
locales observées ; trois sondages signalent l'atteinte de leur plafond
séparé. Les 26 statuts canoniques restent inchangés (474/500).

**Limites maintenues :** un sous-arbre prouvé dans un contexte libre
n'établit pas son rattachement à la phrase, la validité d'une proposition
complète, la cause de l'échec global ou une faute grammaticale. Une
absence de preuve après 12 000 unités signifie seulement *non observé*.
Ce sondage ne s'exécute pas si la forêt canonique a déjà saturé.

## P2 : couverture des résidus hors scope dialogue

Le nouveau `scripts.probe_unscoped_residuals` sélectionne à partir des
**seules sorties canoniques** les résidus sans racine structurelle et
ceux dont la racine n'a fourni aucune analyse valide, **à condition**
qu'aucune racine dialogue exploitable n'ait déjà justifié un rejeu
scopé. Les 4 saturations de forêt et le timeout initial restent exclus
des tentatives de preuve locale et signalés comme censurés.

Pour la cohorte figée du 7 novembre, cela correspond à **14 relectures**
complémentaires : 8 `no_structural_root` et 6
`roots_without_valid_analysis` non dialoguées. Chacune passe par
`parse_corpus_case` puis le seul `Parser.parse`, sur texte préparé,
budgets 50 000/500 000 et échéance 10 s, avec le sondage interne borné
décrit ci-dessus. Les nouvelles sorties `unscoped_local_probes.jsonl`,
`unscoped_local_probe_summary.json` et
`unscoped_local_probe_report.md` sont jointes à la synthèse par ID
et SHA de cohorte ; toute dérive d'identité/éligibilité provoque un échec.
Une échéance n'est jamais comptée comme absence grammaticale.

**Validation complète sur l'Action
[42422741254](https://github.com/leye0/seman2/actions/runs/42422741254)** :
les **14/14** cas supplémentaires ont produit **406** témoins positifs
locaux. Les sept dialogues en ont fourni à nouveau **521** : au total
**927** preuves sur **21/21** résidus structurels non complétés.
**906** témoins sont mappés exactement à la source *et* à tous les
enfants ; les autres demeurent explicitement non mappés. Sur les 28
sondages locaux distincts (deux par dialogue et un par cas hors dialogue),
**cinq** ont atteint leur budget indépendant. Les cinq cas canoniques
initialement censurés par les ressources sont restés exclus. Le résultat
canonique demeure **474/500**, sans déclaration de faute issue d'une
non-détection.

## P2 : relations de rôles réellement résolues dans les constituants

Une étape additionnelle **postérieure au sondage** transforme seulement
les sous-arbres déjà retenus et localement acceptés en objets `ChartItem`
pour consulter leurs véritables `SyntacticLink`. La relation sujet–prédicat
est conservée sous `independent_local_probe.validated_local_role_pairs`
**uniquement** si :

- les deux liens `subject` et `event`/`predicate` ont réellement des ancres
  lexicales résolues, de la forme `lex:start:end:catégorie:lemme`;
- la tête du sujet possède une catégorie **nominale** reconnue (nom,
  pronom, nom propre, pronom interrogatif), et celle de l'événement une
  catégorie **verbale** reconnue. Une ancre héritée d'un guillemet ou
  d'une copule ne constitue pas une preuve de tête nominale;
- les positions des deux têtes restent **dans leurs enfants respectifs**,
  et ces enfants sont distincts et non chevauchants;
- le tout appartient à la **même composition locale acceptée** déjà
  échantillonnée, avec une règle, des enfants et des spans vérifiables.

Une déclaration statique `exports` dans une règle **ne suffit jamais**.
Le nombre de preuves de rôle est à nouveau borné par `trace_limit`, et
la construction de leurs seuls `ChartItem` est limitée aux constituants
déjà retenus; elle ne relance pas la recherche k-best et ne modifie pas
son budget canonique. Les deux têtes et les enfants sont mappés dans
la source **seulement** si le texte équilibré le permet explicitement.

Cette nouvelle preuve établit une paire de rôles **interne à une lecture
locale**. Elle n'établit pas que cette lecture appartient à un arbre
global, qu'elle est préférable à une alternative, ou qu'elle expose
un désaccord grammatical. Les relations ambiguës, sans ancre lexicale
résolue, sont volontairement absentes plutôt qu'inventées.
