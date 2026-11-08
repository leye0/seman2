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

## P2 : concurrence entre arbres grammaticaux complets

Les comparateurs indépendants (contrôles stricts #76/#244, grammaire
marquée #463/#480) échantillonnent maintenant **au plus quatre arbres
complets** déjà accessibles dans le même `ParseResult`. Aucun nouvel
appel du parseur, budget, texte ou mode grammatical n'est introduit.

`bounded_complete_tree_competition` dans
`dialogue_rejection_comparators.jsonl` conserve, par rang :

- la règle racine et le nombre de déviations **expressément attestées**
  dans cet arbre ;
- les relations sujet/prédicat attestées par la règle marquée sélectionnée
  (mapping exact vers la phrase source) ;
- les couples de têtes sujet/verbe **réellement liés** par une composition
  locale acceptée et appartenant à cet arbre complet, dans une limite
  de 32 couples et 4096 nœuds visités par arbre ;
- les indicateurs de troncature et de censure par délai.

Le document `residual_evidence_synthesis.jsonl` rapproche ces positions
originales des conflits observés dans une **tentative rejetée** du parseur
strict. Une correspondance prouve la coexistence de ces positions dans
une dérivation complète **sous le mode du comparateur** ; elle ne prouve
ni que cette lecture est linguistiquement voulue, ni qu'elle réussit
dans la grammaire stricte. L'absence de correspondance dans quatre arbres
ne démontre rien sur les arbres non échantillonnés.

### Mesures vérifiées sur le corpus gelé (CI `42522241184`, 2026-11-08)

Les contrôles stricts #76 et #244 livrent chacun **4/4 arbres complets
sans déviation marquée**. Les deux cas expérimentaux donnent :

| Cas | Arbres complets marqués | Relation exacte attestée | Sans déviation enregistrée |
|---|---:|---|---:|
| #463 | 4/4 | `your mothers` [63,75] ↔ `was` [76,79] | 0/4 |
| #480 | 4/4 | `they` [59,63] ↔ `says` [64,68] | 0/4 |

Le cas #480 conserve aussi, dans chacun de ses quatre arbres, une **seconde
relation marquée distincte** : `says` [29,33] ↔ `they` [34,38].
Les huit correspondances entre les deux positions de refus strict et
les relations marquées appartiennent à **deux cas sources distincts**,
pas à huit phrases ou huit erreurs indépendantes.

Ce résultat augmente la preuve **sur ces analyses complètes**. Il ne
certifie ni l'exhaustivité des analyses, ni la fausseté grammaticale de
toute interprétation possible, ni une lecture « correcte » imposée par
le sens. La couverture canonique reste **474/500**, avec 26 résiduels,
sans modification de la grammaire ou des budgets 50k/500k/10 s.

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

**Validation sur les 500 cas, après filtrage conservateur :** l'Action
[42430167386](https://github.com/leye0/seman2/actions/runs/42430167386)
conserve les **26** résidus, les **927** compositions positives et
**38** occurrences échantillonnées de paires sujet–prédicat dans
**12** cas. La synthèse indépendante ne trouve que **26 paires distinctes**
après dédoublonnage par cas, règle et offsets source exacts; une paire
sans mapping exact n'est pas fusionnée entre projections. Les 38 sont
des observations répétables de lectures *acceptées localement*, et non
38 relations grammaticales humainement validées. Certaines catégories
lexicales permises demeurent surprenantes en contexte (par exemple une
lecture nominale de « as »); le filtre de catégories ne garantit donc
**ni plausibilité lexicale contextuelle ni arbre global**. Toute future
qualification d'anomalie devra confronter les lectures concurrentes et
établir séparément une incompatibilité effectivement démontrée.

**Comparaison sans nouveau parsing :** la synthèse peut regrouper, par
occurrence source exacte d'une **même tête prédicative et même catégorie
lexicale**, les différentes têtes sujet proposées par ces constituants
acceptés localement. Elle dédouble les observations identiques de
plusieurs relectures, retient règle/scope/catégorie de chaque candidat,
et refuse de regrouper les offsets non mappés. La **re-synthèse** des
artefacts de l'Action ci-dessus trouve **4 cas** (#109, #182, #220, #344)
présentant chacun
une tête prédicative avec **2 têtes sujet candidates**. Le rapport les
expose sous `shared_predicate_local_subject_candidates` ; les indicateurs
`whole_sentence_ambiguity_proven` et `grammatical_conflict_proven`
restent explicitement `false`. Les correspondances source tête/enfant/
constituant sont aussi contre-vérifiées lors de la synthèse.
La validation Layer 1
[42430945036](https://github.com/leye0/seman2/actions/runs/42430945036)
est verte avec **573 tests** et les contrôles de qualité globaux.

## P2 : confrontation de chaque tête résolue au lattice original

Une étape de preuve **additionnelle**, sans nouvelle lexicalisation,
conserve désormais la **lemme de l'ancre syntaxique réelle** et confronte
chaque tête à `LexicalLattice.covering(start, end)` reçu directement de
`parse_corpus_case` avec le `Parser.parse` public. Le témoin indique :

- si une entrée au même span, à la **même catégorie et à la même lemme**
  existe vraiment dans le lattice; le nombre et les provenances de ces
  candidats;
- toutes les **autres catégories proposées au même span** par le même
  lattice, sans en éliminer aucune et sans chercher à établir laquelle
  convient au contexte;
- la surface exacte dans le texte d'analyse, contrôlée de nouveau lors
  de la synthèse, et la correspondance source déjà conditionnée à un
  mapping exact.

La sortie `lexical_lattice_evidence` reste attachée à chacune des deux
têtes de `validated_local_role_pairs`; l'ancien schéma sans cet ajout
reste analysable, mais ne doit **jamais** être compté comme un audit
lexical effectué. Aucune valeur de score lexical n'est interprétée
comme une probabilité de justesse : `contextual_plausibility_proven=false`
et `grammatical_conflict_proven=false` restent obligatoires. Un candidat
manquant indique une insuffisance de provenance de cette tête locale,
**pas** une faute dans la phrase.

**Mesure reproductible (Action
[42441843744](https://github.com/leye0/seman2/actions/runs/42441843744)) :**
le passage canonique reste **474/500**. Les **38 paires** conservées
représentent **76 observations de têtes** (avec doublons possibles entre
relectures) : les **76/76** disposent d'au moins un candidat lexical de
mêmes span, catégorie et lemme; **67/76** présentent **en outre** une
autre catégorie au même span. Ainsi, un accord avec le lattice **n'est
pas** une preuve de validité grammaticale : par exemple, au cas #182,
`as` est trouvé comme `N` en parallèle de `ADV`, `CONJ`, `EQUATIVE-AS`
et `PREP`; `good` comme `N` en parallèle de `ADJ` et `ADV`;
`natured` comme `V` en parallèle de `ADJ` et `N`. Ces lectures
localement unifiées restent des **candidats**, pas des corrections.
L'Action
[42441843750](https://github.com/leye0/seman2/actions/runs/42441843750)
confirme **575 tests** et les contrôles de qualité Layer 1.

## P2 : comparer des atomes de traits réellement matérialisés

Après la vérification des têtes, les mêmes `ChartItem` locaux acceptés
livrent maintenant les traits *de leurs enfants sujet et prédicat*
effectivement matérialisés : `number`, `person`, `vform` et `tense`.
Seules les valeurs **atomiques** du `FeatureStructure` sont retenues;
une variable `?…`, un `TOP`, une disjonction ou un trait absent reste
non comparable. Les atomes `number` et `person` présents sur les **deux**
enfants sont comparés en égalité/différence, avec leurs valeurs
originales, sous `cross_child_grounded_atom_comparisons`.

Le fait de voir `plural` d'un côté et `singular` de l'autre n'est **pas
en soi** une preuve de faute ni même une preuve que la règle locale
exige leur accord : `grammatical_agreement_requirement_proven=false` et
`grammatical_conflict_proven=false`. Pour franchir cette étape il
faudra identifier dans la règle grammaticale elle-même une contrainte
applicable et ses rattachements, et confronter les lectures rivales.
La synthèse recalcule les comparaisons depuis les atomes conservés et
refuse une valeur ouverte ou une conclusion surévaluée. Les anciens
artefacts sans ces observations restent explicitement non mesurés.

**Mesure réelle :** l'Action 500
[42444014909](https://github.com/leye0/seman2/actions/runs/42444014909)
conserve **474/500** et les **26 résidus**. Les **38/38 paires** locales
échantillonnées ont une observation des traits enfants; **27/38** ont
simultanément un atome `number` côté sujet et prédicat. Cela produit
**27 comparaisons de nombre et 27 de personne**, toutes égales dans
ces constituants *déjà acceptés après unification*. Il n'en découle
aucune vérification indépendante de l'accord : une composition peut
propager ses contraintes à l'enfant. Dans le cas #220, un témoin ayant
la tête de surface `I` expose ainsi `person=3` des deux côtés pour
`I`/`was` : c'est la **valeur enfant matérialisée**, pas la preuve que
`I` possède intrinsèquement cette personne. La suite doit distinguer
les traits d'origine lexicale des traits obtenus par propagation,
avant de qualifier le moindre conflit. Les 11 autres paires n'ont pas
de comparaison de nombre atomique des deux côtés; leur absence de
valeur est **inconclusive**.

La CI globale
[42444014895](https://github.com/leye0/seman2/actions/runs/42444014895)
est verte : **577 tests**, contrôles de qualité Layer 1 et smoke.

## P2 : vérifier les égalités réellement déclarées par les règles grammaticales

La comparaison de deux enfants déjà unifiés ne suffit pas à démontrer
qu'une règle *exige* leur accord. Le sondage local consulte désormais
la règle **exactement utilisée par la composition retenue**, dans le
même `_LazyMaterializer`, en vérifiant son identifiant, sa longueur RHS
et les catégories de ses enfants. Pour les positions portant des liens
réellement résolus `subject` et `event`/`predicate`, la preuve expose
les termes RHS de `number` et `person`. Elle reconnaît une égalité
**directement exprimée** lorsque les deux positions RHS partagent la
*même variable d'unification* pour ce trait (p. ex. `?n` dans
`clause_np_vp` sur `NP` et `VP`). Une règle sans variable partagée
reste **non concluante** sur les contraintes indirectes : son silence
ne prouve pas l'absence d'autres contraintes.

Cette preuve est syntaxique et compositionnelle, sans classement
lexical contextuel ni interprétation sémantique. La synthèse recalcule
les égalités à partir des deux côtés de la règle, refuse une preuve
surévaluée et traite les artefacts historiques comme non mesurés.
Même lorsqu'une égalité locale RHS est établie, elle **ne démontre pas
la grammaticalité ou la faute de la phrase entière** : les caractères
originaux, alternatives, rattachements complets et contraintes lexicales
indépendamment établies doivent encore être vérifiés.

**Mesure du rejeu réel** :
[42446924524](https://github.com/leye0/seman2/actions/runs/42446924524)
préserve **474/500**, les **26** résidus et les **38** couples locaux.
**26/38** ont une égalité directe de `number` **et** de `person`
déclarée par leurs RHS : **25** compositions `clause_np_vp` et **1**
`wh_supplementary_subject_comma`. Parmi les **27** paires possédant
des atomes de nombre comparables, **une** (`wh_obj_clause`) ne porte
pas de variable RHS partagée sur les deux rôles. Cette différence
démontre pourquoi comparer des atomes déjà unifiés ne suffisait pas.
Les **12** autres paires restent *non prouvées par ce contrôle direct*,
et non fautives par défaut. Les **580 tests**, les contrôles de qualité
et le smoke sont verts dans
[42446924528](https://github.com/leye0/seman2/actions/runs/42446924528);
les tests de dialogue de
[42446924515](https://github.com/leye0/seman2/actions/runs/42446924515)
sont également verts.

## P2 : séparer les traits du candidat lexical sélectionné des traits unifiés

Une feuille `ChartItem` retenue possède son `lexical_candidate` original.
Le sondage descend désormais **dans le véritable enfant matérialisé**
et n'accepte une observation de traits initiaux que si **une seule**
feuille possède exactement le span, la catégorie et la lemme de l'ancre
syntaxique résolue. Il relève uniquement les atomes déjà présents de
`number`, `person`, `vform` et `tense` sur ce candidat, sans inventer
de valeurs ni retenir une autre lecture du lattice. Les valeurs
ouvertes, les feuilles absentes et les identités non uniques sont
explicitement non probantes.

La synthèse compare séparément ces atomes **pré-unification** aux
atomes de l'enfant NP/VP **post-unification**, puis les deux candidats
lexicaux sélectionnés si les deux côtés possèdent un trait atomique.
Elle recalcule et valide toutes les comparaisons, l'identité des têtes
et la provenance des feuilles, et refuse toute conclusion de faute.
Un candidat lexical demeure une **hypothèse morphosyntaxique** : même
une opposition attestée entre ses traits et ceux d'une règle locale
n'établit pas encore que la phrase originale est agrammaticale.
Cette étape n'évalue ni signification ni plausibilité contextuelle.

**Résultats mesurés**, [Action 42486130297](https://github.com/leye0/seman2/actions/runs/42486130297) :
le strict demeure **474/500**, avec **26** résidus, **38** couples
sujet/prédicat locaux et **26** obligations directes de `number` et
`person` dans leurs règles. Les **76/76 têtes** ont une **feuille
lexicale sélectionnée unique** au span/catégorie/lemme exacts.
Seules **10/38 paires** ont deux atomes *lexicaux originaux* de
`number` comparables (10 égalités), et **6/38** ont deux atomes de
`person` comparables (6 égalités). Sur les paires à égalité RHS
directement déclarée, la preuve lexicale des deux côtés est présente
pour **9** comparaisons de nombre et **5** de personne. On observe
**zéro différence** entre atome lexical et atome d'enfant lorsque les
deux sont effectivement renseignés. L'absence de comparaison n'est
pas une confirmation d'accord.

**Contre-exemple de provenance #220 :** la paire locale de surface
`I was` dont l'enfant sujet est unifié avec `person=3` sélectionne
en réalité une tête `I` **catégorie `N`, lemme `i`**, sans personne
lexicale d'origine. La troisième personne n'est donc **pas une
propriété intrinsèque prouvée de ce `I`**; elle est obtenue via
la composition. Cela montre pourquoi les 27 égalités initiales
entre enfants post-unification ne permettaient aucun jugement
grammatical autonome. Aucune faute de phrase n'est inférée.
La CI complète
[42486130169](https://github.com/leye0/seman2/actions/runs/42486130169)
est verte (**583 tests** et contrôles Layer 1).

### P2 : séparer les rejets de règles des lectures lexicales rejetées

Un relevé complémentaire sur les **mêmes traces bornées**, sans nouveau
parse, recalcule chaque contradiction atomique `required` / `offered`
à partir des deux structures de traits d'origine. Il sépare :

- **Rejet d'une tentative de règle** (`rule_*` avec `rule_id`) : conflit
  de contraintes grammaticales de cette branche précise.
- **Rejet d'une lecture lexicale candidate** (`lexical_*` sans règle) :
  ne témoigne pas, à lui seul, d'un accord sujet/prédicat incorrect.

Dans les **7** traces de dialogue échantillonnées : **78** conflits
`voice`, **3** `vform` et **2** `pronominal` dans les tentatives de
règles; les lectures lexicales rejetées ont notamment **15** conflits
`number` et **43** `vform`. Dans les **14** traces non restreintes :
**57** conflits de `voice`, **8** de `stype`, **7** de `vform` pour
les règles; **16** `number`, **47** `vform` pour les lectures lexicales.
**Aucun conflit de `number` ou de `person` n'est observé dans les
tentatives de règles de ces deux échantillons.** C'est une limite des
traces, non une preuve d'absence de fautes d'accord dans le corpus.

Fait plus discriminant : **7** occurrences échantillonnées de rejet de
règle ont aussi une analyse **localement acceptée indépendamment** pour
la **même règle, la même catégorie et les mêmes spans d'analyse et
de source exacts** (4 dans les traces dialogue, 3 non restreintes).
Ce ne sont *pas* deux résultats de la même dérivation : le rejet se
produit sous une demande de traits différente, typiquement `voice=passive`
face à une règle active, tandis que la composition locale acceptée est
prouvée dans son propre contexte. Cela invalide le raccourci « rejet de
branche = règle impossible = faute dans la phrase ». Le relevé est
échantillonné, non exhaustif, et n'établit aucun diagnostic de phrase.

### P2 : contrainte grammaticale locale réelle sur une feuille rejetée

Les rejets lexicaux ne sont pas tous de simples *hints* : un rejet
`lexical_unification` provient de la matérialisation d'un enfant sous
les traits exigés par une **case RHS d'une règle précise**. La trace
contient sa dernière requête (`via_rule_id`, `via_child_index`). Le
rapport P2 conserve cette provenance uniquement lorsque catégorie,
span d'analyse, span de source **exact** et surface originale du mot
s'accordent; il recalcule également les deux atomes en conflit. Les
rejets `lexical_hint_unification` sont exclus de ce niveau de preuve.

Dans les **7** traces de dialogue, **13** événements de matérialisation
répétés se réduisent à **7** conflits distincts de case grammaticale
au span de source exact : **3** de `number`, **2** de `vform` et **2**
de `subcat`. Les contrôles marqués donnent **20** événements pour
**8** conflits distincts (**3** de `number`, **2** de `vform`, **3**
de `subcat`); les traces non restreintes ne livrent pas de témoin de
ce type dans leur échantillon conservé.

Exemple du cas **480**, lecture candidate `says` à la source `[64,68]`
dans `dialogue_speech_tag_post` RHS `[1]` : la case demande
`number=plural`, mais le candidat singulier offre `number=singular`.
C'est bien une **incompatibilité locale entre le mot proposé et une
contrainte de règle**. Le cas 480 a, *séparément*, deux écarts d'accord
prouvés par son arbre **marqué opt-in**; on ne les infère pas de ce
rejet isolé, qui ne prouve ni rattachement sujet–prédicat ni erreur de
phrase. Ce contrôle reste exclusivement morphosyntaxique (Layer 1).

### P2 : sujet matérialisé avant une lecture verbale incompatible

Une instrumentation **opt-in** supplémentaire associe un rejet lexical
`lexical_unification` aux enfants **déjà matérialisés** aux positions
précédentes du **même essai de combinaison RHS**, au moment où le verbe
est demandé. Le rapport ne retient un conflit sujet/prédicat que si :

- l'enfant antérieur est un `NP` dont la position de règle exporte
  explicitement `referent=subject*` ou `referent=speaker` ;
- la position courante est `V` ou `COPULA` et exporte un `event` ;
- les deux positions partagent littéralement la même variable RHS
  (`number` ou `person`), et la valeur atomique du NP matérialisé est
  celle qu'exige le contexte du verbe ;
- le candidat verbal offre un atome opposé, et les positions du sujet
  et du verbe sont chacune repérées **exactement** dans le texte source.

Cette preuve n'exige **aucun raisonnement lexical ou sémantique** :
elle s'appuie uniquement sur la règle grammaticale, les traits
morphosyntaxiques et deux morceaux réellement visités lors du même
essai. Le sujet a été accepté **dans cet essai partiel**, pas
nécessairement sous la bonne lecture intrinsèque du texte; le verbe,
la règle complète et la phrase ne l'ont **pas** été. `same_rule_attempt`
ne doit donc jamais être présenté comme `sentence_fault_proven`.
Les traces antérieures ne contenaient pas ces frères antérieurs. La
nouvelle [Action 42508955694](https://github.com/leye0/seman2/actions/runs/42508955694)
confirme **deux témoins distincts dans le texte source** : #463,
`your mothers` `[63,75]` (NP pluriel) face à `was` `[76,79]`
(COPULA singulier), contrat commun `?n_whr` ; #480, `they` `[59,63]`
(NP pluriel) face à `says` `[64,68]` (V singulier), contrat commun
`?n_tag`. Le premier apparaît en rejeu dialogue et en contrôle marqué,
le second en contrôle marqué : **3 observations cumulées entre canaux, mais
seulement 2 conflits source distincts**. Aucune n'est comptée comme
faute prouvée de la phrase par ce seul instrument. La couverture
canonique reste **474/500**.

### P2 : vérifier l'atome lexical d'origine de la tête nominale

La preuve précédente conserve un `NP` **après** unification. Son atome
`number` peut provenir du contexte grammatical et non de ses mots.
Le nouveau niveau de preuve descend donc dans **ce même NP matérialisé**,
lit l'ancre nominale `head`/`referent` réellement exportée, exige une
seule feuille lexicale sélectionnée avec exactement les mêmes span,
catégorie et lemme, puis lit ses traits initiaux non unifiés.

La synthèse compare `number`/`person` du candidat lexical original
du sujet, la valeur du NP matérialisé et la valeur exigée par la
variable RHS commune. Les trois doivent être le **même atome explicite**;
le candidat verbal rejeté doit proposer un atome différent. Si la tête
est un guillemet, une copule, un ancrage absent/ambigu, un candidat
sans atome ou un span non exactement projeté, ce second témoin n'est
**pas** établi. Il n'existe toujours aucun verdict automatique sur
le texte source ni sur l'intention de l'auteur.

**Résultat du rejeu**
[42520753139](https://github.com/leye0/seman2/actions/runs/42520753139) :
les **2** conflits source distincts franchissent aussi ce seuil plus
strict. #463 : la tête `mothers` (N, lemme `mother`, source `lexicon`)
au span `[68,75]` porte intrinsèquement `number=plural` face à `was`
singulier `[76,79]`; #480 : `they` (PRONOUN, `lexicon`) au span
`[59,63]` porte `number=plural` face à `says` singulier `[64,68]`.
La trace dialogue retient **1** conflit, les contrôles marqués **2**,
avec #463 commun aux deux : on compte **2**, non 3, conflits sources.
Les traits de leur NP après unification et leurs variables RHS
correspondent aux mêmes atomes. Le candidat lexical est attesté
comme **sélectionné dans cette tentative**, pas comme intention
linguistique certaine de l'auteur. Les 500 cas restent à **474/500**.
