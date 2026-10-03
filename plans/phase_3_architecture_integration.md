# Passe 3 — Architecture et intégration systémique

> Ce document contient des chaînes de validation transitoires. Le graphe cible
> du runtime continu est `plans/runtime_service_graph.json`. Les répertoires
> `poc/*/output` et les évaluations externes n'appartiennent jamais au chemin de
> données cognitif de production.

## Résultat

La première chaîne de proto-services est exécutable avec :

```bash
./scripts/seman2 phase3
```

Elle ne remplace pas les POCs locales. Elle transforme leurs capacités déjà
vérifiées en composants reliés par des frontières exécutables et auditées.
L'exécution écrit `manifest.json`, `result.json` et `trace.jsonl` sous
`output/phase3/`; ces résultats sont reproductibles et ne sont pas suivis par
Git.

La chaîne contrôlée actuelle et la chaîne Parquet sont des échafaudages
d'intégration, pas encore le runtime continu final. En particulier, le service
transitoire `AnalysisService` qui relit une sortie DLG-03 devra disparaître au
profit du dispatcher d'analyses vivant.

## Séparation des plans

- **processing plane** : observations persistantes → analyses natives →
  fragments → hypothèses → état → retrieval → beam actif;
- **cognitive control plane** : Soar reçoit seulement le contexte actif borné,
  gère buts/opérateurs/requêtes et sélectionne les transformations;
- **memory plane** : graphes, épisodes, hypothèses et indexes disk-backed;
- **evaluation plane** : POCs, oracles exacts et éventuelle revue OpenRouter,
  entièrement hors du runtime.

Une POC de haut niveau doit appeler les mêmes services que le runtime et
consommer leurs identifiants d'artefacts. Elle ne doit pas relire directement
le dossier `output` d'une POC plus basse. Les sorties de POC sont des preuves,
pas un bus de données.

## Runtime vivant et reprise

Le runtime est maintenu en mémoire tant qu'il tourne, mais les classes de
mémoire restent distinctes : caches chauds des services, Active Context, beam
borné, working memory Soar et mémoire globale durable. Le corpus complet ne va
jamais dans la working memory.

La reprise est un checkpoint coordonné. L'installation Soar confirme que
`save agent` couvre mémoire procédurale, mémoire sémantique et plusieurs
réglages; `smem --backup` et `epmem --backup` couvrent leurs bases. Cela ne
démontre pas qu'un seul fichier restaure toute la working memory courante. Le
checkpoint doit donc aussi conserver l'Active Context, le beam, les watermarks
des stores, les travaux en vol, l'offset de replay des entrées et la graine
aléatoire. Au redémarrage, la WM est reconstruite depuis ce snapshot attribué,
puis seuls les événements postérieurs au watermark sont rejoués.

La première boucle inter-époques est exécutable dans RUN-03. À l'époque 0,
Soar sélectionne une hypothèse de question et demande `retrieve-answer`. Le
retrieval résout une référence vers une réponse Parquet réelle. À l'époque 1,
la réponse brute devient une source durable, une unité phrastique attribuée
repasse par ACE/ERG et Dynamic Syntax, puis les fragments, contraintes,
hypothèses, état, épisode et beam alimentent Soar. Les états et épisodes de
l'époque 1 référencent explicitement ceux de l'époque 0; Soar produit alors
`assess-answer`. La reprise reconstruit ce nouveau contexte et reproduit les
mêmes décisions.

RUN-04 prolonge ce chemin avec une frontière de transformation explicite.
`assess-answer` produit trois candidats attribués; de vraies productions Soar
les proposent comme opérateurs, établissent une préférence conditionnelle et
appliquent le choix. Chaque conversation d'essai est isolée dans son propre
contexte opérateur. Le nouvel état d'époque 2 rattache la réponse comme candidat
d'évidence, sans affirmer sa vérité et sans fermer le QUD. Sans provenance
directe et contenu parsé, la préférence disparaît et l'impasse est exposée au
lieu d'être masquée par une valeur par défaut.

## Chaîne et responsabilités

| Service | Entrée | Sortie | Responsabilité |
|---|---|---|---|
| `observation` | `request` | `observation` | Valider et figer le texte observé. |
| `analysis` | `observation` | `analysis-bundle` | Charger les sorties réelles ACE/ERG et Dynamic Syntax de DLG-03. |
| `semantic-projection` | `analysis-bundle` | `semantic-candidates` | Extraire un candidat commun tout en conservant les valeurs natives séparées. |
| `temporal-context` | `semantic-candidates` | `temporally-qualified-candidates` | Construire les relations formelles E/R/S sans inventer de date. |
| `dialogue-state` | `temporally-qualified-candidates` | `dialogue-state` | Créer faits proposés, obligations, contraintes temporelles et delta réversible. |
| `hypothesis` | `dialogue-state` | `hypothesis-set` | Matérialiser les alternatives et leurs justifications. |
| `retrieval` | `hypothesis-set` | `active-beam` | Borner le jeu de travail sans supprimer le jeu persistant. |
| `decision` | `active-beam` | `selection` | Choisir une hypothèse compatible par une politique déclarée. |
| `planning` | `selection` | `communicative-plan` | Construire un plan de contenu inspectable. |
| `realization` | `communicative-plan` | `realization` | Appeler réellement SimpleNLG depuis le contenu symbolique. |

Le manifeste produit à l'exécution expose aussi les dépendances directes. Le
constructeur refuse un service dupliqué, une dépendance absente ou deux types
de frontière incompatibles.

## Contrat de transport

Chaque message possède obligatoirement :

- un type, un identifiant et un identifiant de corrélation;
- le producteur responsable;
- les identifiants parents;
- une charge JSON sérialisable;
- la provenance accumulée et les pertes déclarées;
- une empreinte SHA-256 canonique.

Chaque service vérifie le type reçu et ses champs indispensables. Il n'existe
ni conversion implicite, ni récupération silencieuse, ni remplacement d'une
sortie externe absente par une fixture inventée. Une violation lève
`ContractError`; la commande rend alors `NO-GO` et un code non nul.

## Matière réellement traversée

Le scénario intégré est `John likes Mary.`. L'analyse n'est pas une structure
fabriquée par la chaîne : elle provient de `poc/dlg-03/output/results.json`,
qui contient les sorties ACE/ERG et Dynamic Syntax. La projection lit le MRS,
résout les variables des entités nommées et recoupe ce qui est effectivement
présent dans la sortie TTR. La réalisation finale compile un petit adaptateur
Java temporaire et appelle le JAR SimpleNLG installé localement.

Cette intégration a révélé une limite auparavant masquée : dans ce cas, la
sortie Dynamic Syntax exprime le prédicat et le sujet mais ne lie pas
distinctement Mary comme objet dans sa sémantique finale. Le service ne prétend
donc pas à une identité entre MRS et TTR. Il inscrit une
`partial-correspondence`, déclare la perte `Dynamic Syntax object binding
unresolved`, conserve les deux valeurs natives et fonde la proposition complète
sur ERG seulement.

## Échantillon représentatif des Parquet canoniques

La chaîne de planification ne repose plus uniquement sur la phrase contrôlée.
La commande suivante lit les vrais Parquet Stack Overflow :

```bash
./scripts/seman2 sample-corpus
./scripts/seman2 plan-services
```

Il s'agit d'un **échantillon de couverture opérationnelle**, pas d'une
estimation statistique de tout Stack Overflow. Trois critères déterministes
forcent la présence de phénomènes différents :

- question contenant code et réponses de scores divergents;
- marqueur de discours temporel;
- négation ou incertitude.

Pour éviter un échantillon entièrement local à un seul fichier, cinq shards de
questions régulièrement espacés et leurs cinq shards de réponses sont
considérés. Chaque couple est traité isolément; seuls son meilleur candidat et
au plus trois réponses sont retenus. La sélection actuelle contient trois
questions réelles et neuf réponses, avec fichier canonique, fichier source,
position source, identifiant source et empreinte du corps brut.

Le HTML brut est conservé. La projection texte est une valeur dérivée et ne le
remplace jamais.

### Garde-fous mémoire

- DuckDB : `threads=1`, `memory_limit=256MB`;
- traitement d'un seul couple de shards à la fois;
- espace temporaire limité à 512 Mo;
- trois questions et neuf réponses au maximum en sortie;
- batch d'analyse limité à seize observations et délai maximal de 60 secondes;
- bibliothèques numériques limitées à un thread dans le worker.

Le premier plan simultané sur cinq shards a correctement été refusé par le
plafond DuckDB avant de mettre la machine en danger. L'algorithme séquentiel qui
l'a remplacé a mesuré environ 374 Mo de RSS maximale pour l'échantillonnage et
332 Mo pour la chaîne complète sur cette machine, très loin des plusieurs
gigaoctets qui avaient fait tomber VS Code.

### Résultat observé sur la vraie matière

Les trois titres produisent chacun trois analyses ACE/ERG réelles. Dynamic
Syntax s'arrête après deux actions sur chacun d'eux et ne produit aucune
sémantique finale. Ce résultat est conservé comme preuve négative; aucune
sortie TTR n'est inventée et l'échec d'un producteur n'annule pas le succès de
l'autre.

Le ledger contient donc six entrées : trois succès ERG et trois échecs Dynamic
Syntax. L'adaptateur MRS produit neuf fragments attribués, conserve les neuf MRS
natives et ne sélectionne aucun candidat. Chaque fragment contient variables,
prédicats, rôles, portées et contraintes de handles.

La projection des traits MRS observe ensuite :

- trois candidats au présent, projetés en contraintes formelles E/R/S;
- six candidats sans temps exploitable, conservés comme temporellement
  sous-spécifiés;
- aucune coordonnée calendaire inventée;
- les labels grammaticaux externes ne deviennent pas des primitives cognitives.

Le verdict précis est donc
`GO-INGESTION-ERG-MRS-HYPOTHESES; NO-GO-DYNAMIC-SYNTAX-COVERAGE`. Il ne bloque pas les
services compatibles avec les MRS et empêche en même temps de prétendre que la
couverture multi-formalisme est déjà acquise.

## Plan des proto-services fondé sur les observations

| Service | État | Prochaine frontière |
|---|---|---|
| `corpus-sampling` | implémenté | Généraliser ensuite à Reddit sans jointure globale. |
| `corpus-observation` | implémenté | Ajouter segmentation corps/code/réponses avec alignements. |
| `live-external-analysis` | implémenté | Isoler d'autres producteurs avec les mêmes limites. |
| `analysis-ledger` | implémenté | Stockage persistant append-only. |
| `mrs-graph-adapter` | implémenté | Stabiliser le contrat de fragment commun. |
| `mrs-feature-projection` | implémenté | Étendre temps/aspect sans résoudre les inconnues par défaut. |
| `ttr-adapter` | bloqué par couverture observée | Conserver les parses partiels; élargir lexique/grammaire séparément. |
| `cross-representation-linker` | après adaptateurs | Correspondances explicites, jamais identité implicite. |
| `candidate-hypothesis-ledger` | implémenté | Neuf hypothèses persistantes, aucune sélection et aucun produit 3×3×3 matérialisé. |
| séquence question-réponses | implémenté dans RUN-03 | Étendre de la première réponse récupérée à plusieurs tours et à une vraie politique de pertinence. |

## Invariants GO

Une exécution est `GO` seulement si tous ces invariants tiennent :

- le même identifiant de corrélation traverse tous les services;
- chaque message désigne son parent immédiat;
- tous les producteurs et toutes les empreintes sont présents;
- les analyses externes ne sont pas fusionnées;
- les relations temporelles utilisent explicitement E/R/S et aucune coordonnée absolue n'est inventée;
- les trois hypothèses persistent lorsque le beam actif est borné à deux;
- le contenu sélectionné est celui que reçoit la réalisation;
- la réalisation n'ajoute aucun contenu.

Le test négatif avec une observation inconnue donne `NO-GO` au service
d'analyse. Les tests couvrent aussi entrée vide, mauvais type de frontière,
parents dupliqués, dépendance insatisfaite, topologie du manifeste, chaîne
réelle, rétention des alternatives et relecture de la trace.

## Portée démontrée et frontières restantes

Le `GO` est celui d'une chaîne intégrée initiale, pas celui de toute
l'architecture cognitive. Le service d'analyse couvre actuellement un cas dont
les sorties externes ont déjà été produites. La décision utilise une politique
formelle déterministe; X-03 reste la preuve séparée de passage du beam dans
Soar. Le moteur d'état compositionnel complet, la sélection sémantique de la
réponse, la planification communicative et les scénarios de plus de deux
époques restent à brancher sans élargir artificiellement ce verdict. RUN-03
démontre toutefois que l'état et l'épisode sont réellement chaînés entre une
question et une réponse issue des Parquet, plutôt que simulés par deux fixtures
indépendantes.

## Vérification

```bash
source scripts/activate_local.sh
python -m unittest -v tests/test_phase3_runtime.py
./scripts/seman2 phase3
```
