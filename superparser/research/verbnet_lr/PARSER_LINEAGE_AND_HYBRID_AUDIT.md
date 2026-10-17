# Seman2: audit de filiation des parseurs et proposition d'hybride

Date de l'audit : 17 octobre 2026. **Branche de recherche uniquement.**
Aucun changement au parseur de production (`main`) n'est impliqué.

## Contrat du Layer 1

Le Layer 1 doit produire un arbre grammatical ou une forêt d'analyses
**complètes**, sous un format syntaxique classique: groupes nominaux (NP),
verbaux (VP), prépositionnels (PP), propositions (CLAUSE), spans, règles,
accord/traits, parenté/rattachement, ancres, fonctions syntaxiques et analyses
alternatives. L'interprétation des entités, des événements et des
transformations est un stade **distinct**. Un hit de regex, une suite de POS
ou un constituant partiel ne peut pas tenir lieu d'analyse complète.

Ce contrat existe déjà dans le dépôt:
- `superparser/seman_parser/engine.py`: `Parser.parse()` utilise
  `VectorGrammar.parse_lattice`; `Parser.parse_diagnostic` élargit le k-best.
- `superparser/seman_parser/vector_chart.py`: forêt de constituants et états
  partiels partagés, reconnaissance structurale et extraction k-best paresseuse
  tenant compte des traits. Contrairement à C, aucune limite de deux variantes
  **par case syntaxique** durant la phase de reconnaissance.
- `superparser/seman_parser/chart.py`: `ChartItem`, `PackedNode`,
  `ParseResult`, dérivations avec enfants.
- `superparser/seman_parser/syntax.py`: `SyntacticPackage`, ancres lexicales
  et `SyntacticLink` pour les rôles syntaxiques.
- `superparser/seman_parser/semantic_rules.py` et `semantics.py`:
  interprétation après sélection d'une dérivation via `ParseReport.interpret`.
- `mentions.py`, `refdetect.py`, `discourse.py`: extraction de mentions
  et suivi référentiel à partir des syntaxes produites.
- `segmentation.py`: lattice de candidats morphosyntaxiques, multi-mots,
  contractions et lectures alternatives.

**Constat fondamental** : le moteur vectoriel historique n'a PAS été
remplacé dans `main` par le L-R de recherche. Le `SemanCompiledReader`
est encore étiqueté *research / proof of concept*, même si nos benchmarks
récents ne mesuraient que lui et semblaient décrire « le parseur Seman2 ».

## Reconstitution de l'évolution vérifiable

| Période | Système | Forces démontrées | Limites / régressions |
|---|---|---|---|
| 7 oct. | TRIPS externe, projections syntaxe/sémantique | Parseur riche, analyse structurée | ~908 ms par phrase dont 87% passés dans TRIPS; plusieurs phrases ensemble très coûteuses. `archives/plans/archives-03/analyse_performances.md`. |
| 8 oct. | `chart.py` avec forêt | Ambiguïtés, traits et arbres explicites | Médiane 332 ms sur 40 phrases, p90 9 813 ms, extrêmes à 37,9 s au début. `superparser/PERFORMANCE.md`. |
| 8–10 oct. | Index, signature des dérivations, dédup, sémantique différée | Moins de copies/combinaisons, forêt conservée, qualité non régressée sur petites séries | Des micro-optimisations ont parfois détérioré la médiane; les benchmarks ne sont pas tous comparables. |
| 10 oct. | `vector_chart.py` + k-best paresseux, segmentation inter-propositions | Roman *The Map of Everything*: 2 663 / 3 326 phrases complètes sous timeout de 1 s, 614 timeouts; p50 80,4 ms sur les réponses rendues; corpus référence 300/300, p50 ~14 ms, p95 ~85 ms | Couverture 80% tout compris sur le roman; 300 phrases de référence liées à l'évolution du système; exactitude normalisée du meilleur arbre ~75%, non pas 100% gold. |
| 11–14 oct. | Prédictif entraîné `predictive.py` | 50 premières phrases, p50 6,12 ms et 50/50 couvertes; morphologie et tree materialization différée | Sur 300 phrases: 272/300 complétées et p95 2 176 ms; p95 catastrophique dû aux reprises. |
| 14–15 oct. | Prédictif V2 à recherche partagée | 300/300 et p95 ~86 ms sur le corpus de référence | p50 ~20 ms, exactitude normalisée du meilleur arbre ~56%, inférieure aux ~75% du vectoriel. |
| 15–17 oct. | L-R compilé `reading_kernel_compiled*.py` | Latences très basses, projections de traits et grammaire réelles | Parcours presque monotrajet: faible couverture sur longues phrases et 44/120 cas annotés terminés. |
| 16–17 oct. | Snapping d'arbres complets, sous-arbres partiels, C hiérarchique | Structures cachées, chemins de grammaire recombinés, arbres locaux nouveaux jamais observés exactement | Ne sort pas encore la forêt globale nécessaire au Layer 2; aucun gain démontré de qualité globale; recherche bornée et suracceptation non évaluée pour C. |

Sources anciennes : `superparser/PREDICTIVE_POC.md`,
`superparser/predictive_benchmark.json`,
`superparser/predictive_v2_benchmark_300.json`,
`superparser/BENCHMARK_THE_MAP_OF_EVERYTHING.md`,
`superparser/REFACTOR_PERFORMANCE.md`, et
`archives/plans/archives-03/Seman2_Parser_Blueprint_TRIPS.md`.

### Prototype hybride oublié

`superparser/refactor/overlay/seman_parser/fastpath.py` contient déjà:
- lattice de signatures lexicales avec **toutes** les catégories,
- trie de constructions avec alternatives,
- reconnaisseur de structures de type Earley (sans traits),
- apprentissage de patrons à partir du chart,
- façade `FastParser` qui **conserve** `Parser.parse()`.

Il était expérimental et la documentation
`superparser/refactor/README.md` indique que ses gains complets et
ses ambiguïtés n'avaient pas encore été validés sur 850 phrases. Il est
une piste de **réutilisation** à auditer et non une preuve que l'hybride
existe déjà en production.

## Comparaison à protocole identique (nouvel audit)

Workflow:
https://github.com/leye0/seman2/actions/runs/39039026916

La comparaison exécute les 120 mêmes phrases d'assertions positives et
les 24 mêmes négatives (et leurs contrastes) sur les deux moteurs, avec
la même grammaire/WordNet et le cache texte désactivé.

| Mesure | Vector forest | L-R compiled |
|---|---:|---:|
| Phrases complètes / 120 | **120** | 44 |
| Toutes assertions positives présentes / 120 | **115** | 34 |
| Arbres complets avec syntaxe / 120 | 120 | 44 |
| Négatives artificielles acceptées / 24 | **19** | 6 |
| Phrases de contraste grammaticales terminées / 24 | 22 | 6 |
| p50 sur positives | 7,48 ms | 2,615 ms |
| p95 sur positives | 26,9 ms | 5,404 ms |
| p99 sur positives | 411 ms | 6,045 ms |
| Pire cas | 2 703 ms | 6,438 ms |

IMPORTANT: `all_gold_assertions_met` vérifie un **sous-ensemble** de
relations syntaxiques/POS/règles pré-annotés, pas tout l'arbre. Le corpus
est interne, pas une évaluation entièrement indépendante et aveugle.
Le vectoriel utilise les spans lexicaux complets et le L-R du benchmark
la version à un seul token. La latence inclut la vérification des
assertions. Les 19 négatives acceptées montrent un problème réel de
suracceptation: il serait incorrect de traiter le chart vectoriel comme
un *gold teacher* sans garde supplémentaire.

### Signal externe non comparable directement

Sur les romans Gutenberg d'autres auteurs, L-R + snapping exact a
terminé ~1 949 / 50 000; la faiblesse sur >12 tokens est nette. Il
n'existe PAS encore de benchmark vectoriel head-to-head sur les MÊMES
50 000 phrases sous le MÊME budget, donc l'audit ne prétend pas que
le vectoriel atteindra 100% ou 80% sur ces textes.

La POC C a revalidé des sous-arbres de 8–12 tokens jamais vus comme
arbres complets à l'entraînement. Des budgets beam et de temps troncaux
restent problématiques. Cela **ne prouve pas** la capacité d'analyse
globale ni les dépendances sémantiques correctes.

## Verdict architectural: sauver le vectoriel et absorber C

Une seule sortie canonique: `ParseResult` (forêt + alternatives);
chaque analyse valide sélectionnée doit être un `ChartItem` avec
`category`, `rule_id`, `children`, `features`, `syntax`,
`lexical_candidate`, provenance et offsets exacts.

Chemin cible:

1. **Treillis lexical UNIQUE**, incluant toutes les lectures, les
   contractions et les multi-mots. Aucune projection en un seul POS,
   aucune empreinte fondée sur l'égalité des ensembles de sens.
2. **Compilation de C en index d'attentes / constructions apprises**.
   C suggère des expansions/réductions et des îlots/constituants
   vérifiés, sous forme de nœuds/alternatives partagés AVEC règles et
   fonctions grammaticales. Ne jamais appeler un hit C « CLAUSE
   analysée » sans couvrir le texte entier et la syntaxe.
3. **`VectorGrammar` est le moteur canonique de complétion**, avec
   forêt compacte et extraction k-best paresseuse. Injecter les nœuds
   C ré-unifiés dans le chart ou utiliser les patterns comme ordonnancement
   de l'agenda, jamais comme autorisation pour sauter des contraintes.
4. **Représenter les conflits par des alternatives partagées** et
   non un beam arbitraire de 2 ou 4 arbres complets. Éviter la
   réexploration identique. En cas de budget, signaler explicitement
   `partial / unknown` et préserver les sous-structures.
5. **Valider la syntaxe AVANT promotion et sémantique**: accords,
   négation/temps/voix, valence, attachements de PP, relatives/gaps,
   coordonnants, référents/positions et construction-guard. Les
   résultats vectoriels faux positifs actuels sont une priorité,
   pas un détail statistique.
6. **Interpréter ensuite** via `ParseReport.interpret` et la
   mémoire discursive de Seman2, sans déplacer les rôles sémantiques
   dans les patterns eux-mêmes.

Les variantes répétitives/optionnelles du C ne doivent pas supprimer
les informations NP/VP/PP/CLAUSE et les exports sujet, objet, adjunct,
etc.; ce sont des façons compactes de COMPILER les règles classiques.

## Étapes testables avant fusion dans main

### 0 — Geler un contrat de qualité

Corpus d'assertions 120 cas, 24 négatives, 300 phrases de référence,
le roman original `The Map of Everything`, les deux romans Gutenberg
à auteurs distincts, et des arbres gold avec vrais rattachements.
Versionner le protocole, parser mode, corpus, budgets, WordNet et CI.
Tout hit de motif sans arbre complet est une réussite *locale* seulement.

### 1 — Restaurer la baseline complète

Maintenir un workflow qui vérifie que le `Parser` vectoriel retourne
des racines typées, children, traits, spans et liens valides. Mesurer
les négatives (19/24 sur cet audit) et les catégoriser par cause.
Les règles positives doivent coexister avec des preuves négatives:
`requires` et contraintes de valence, pas listes d'exceptions.

### 2 — Brancher C en CONSEILLER du chart

Le match C doit retourner des arbres/nœuds packés et leurs
provenances, pas seulement (cat, début, fin, score). Mesurer trois
modes sur les mêmes inputs: chart seul, chart avec priorité C, chart
avec injection de sous-structures ré-unifiées. Vérifier identité de
résultat avec oracle large et k-best plutôt que cache hits seuls.

### 3 — Corriger la discrimination grammaticale

Localiser les 19 fausses acceptations du vectoriel, analyser leurs
règles gagnantes et sens lexicaux, séparer mauvais classement,
dérivation grammar-licensed mais fausse, et trous lexicaux.
Conserver les arbres vrais dans les alternatives; négatives
ne peuvent pas être acceptées plus souvent qu'avant le changement.
Augmenter progressivement la suite indépendante.

### 4 — Déterminer le budget et la vitesse

Autoriser jusqu'à 500 ms pour explorer l'architecture, avec un mode
hors ligne plus coûteux pour créer des témoins. Contrôler p50/p95/p99,
coûts lexicaux, forêt, mémoire, troncatures, et nombre d'analyses
STRUCTURELLEMENT distinctes; vérifier que les limites sont de vrais
délais, pas des limites internes de variant beams.

### 5 — Éprouver la généralisation

Exécuter en aveugle sur les mêmes phrases Gutenberg et une référence
externe de syntaxe annotée, avec étiquettes de rôles. Gagner en
couverture et en fidélité syntaxique, pas seulement en hits.
Maintenir les hypothèses multiples, traquer la provenance et
n'apprendre en ligne que des patrons soutenus puis validés.

## Décision

**Ne pas remplacer le Layer 1 par le L-R ni par C.** Ne pas non plus
déclarer le moteur vectoriel déjà correct: il suraccepte les négatives.

Repartir de `engine.Parser + VectorGrammar + SyntaxPackage` comme
contrat de sortie, puis **récupérer** les optimisations sûres des
lecteurs rapides (lattice partagé, index, score de transition,
traitement paresseux) et les généralités grammaticalement
contraintes de C à l'intérieur de la forêt. Toute optimisation
devra prouver qu'elle ne supprime pas les analyses licites.
