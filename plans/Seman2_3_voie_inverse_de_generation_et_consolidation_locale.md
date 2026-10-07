# Seman2 V3 — Voie inverse de génération et consolidation locale

## Plan d’implémentation

Ce document complète `Seman2_Architecture_3_Niveaux.md`. Il ne remplace pas
la constitution ni les invariants de cette architecture. Il précise comment
implémenter :

- la consolidation des observations du niveau 3 ;
- les appels réels à disco-dop, AtomSpace et OpenCog Miner installés localement ;
- le reprocessing des anciennes observations ;
- la voie inverse `sens → structure → surface` ;
- la provenance, les échecs et la reprise de ces opérations.

Le document décrit la cible de développement. La section « État au moment de
la rédaction » distingue ce qui existe déjà de ce qui reste à construire.

---

# 1. Invariants non négociables

## 1.1 Exécution locale seulement

TRIPS, disco-dop, AtomSpace, OpenCog Miner et leurs dépendances doivent être
exécutés sur la machine locale.

Il ne doit exister :

- aucun fallback HTTP ;
- aucun service distant transparent ;
- aucun envoi de texte, de graphe ou de fragment vers une API externe ;
- aucune divergence fonctionnelle silencieuse lorsqu’une bibliothèque locale
  manque.

Une dépendance absente rend la capacité correspondante explicitement
`unavailable`. Elle ne déclenche pas une approximation distante.

## 1.2 Le savoir appris reste de la donnée

La voie inverse ne doit contenir aucun branchement du type :

```python
if semantic_type == "request":
    return "Could you ...?"
```

Les catégories TRIPS, les relations observées, les fragments disco-dop, les
patterns Miner, les alignements et les distributions contextuelles sont des
données. Le code ne connaît que des opérations techniques génériques :

```text
match
retrieve
align
generalize
instantiate
compose
rank
trace
```

## 1.3 Une seule mémoire canonique durable

SQLite/WAL reste la mémoire canonique et rejouable :

- évidence brute ;
- analyses TRIPS natives ;
- projections dérivées ;
- structures apprises ;
- supports ;
- alignements ;
- bindings ;
- dérivations ;
- résultats de génération ;
- états de consolidation.

AtomSpace est une projection locale calculable de cette mémoire. Il ne doit
pas devenir une deuxième source de vérité impossible à reconstruire.

## 1.4 Append-only et révision explicite

La consolidation n’écrase pas une structure déjà apprise. Une nouvelle
généralisation, une fusion, une scission ou un changement de score crée :

- un nouvel objet ;
- une dérivation ;
- des relations explicites vers les objets précédents ;
- une nouvelle révision de score lorsque nécessaire.

## 1.5 Même modèle dans les deux directions

La compréhension et la génération doivent utiliser les mêmes :

- observations sémantiques ;
- observations structurales ;
- fragments ;
- alignements ;
- abstractions ;
- statistiques de contexte ;
- preuves et scores.

La génération ne sera pas un second système à base de templates.

---

# 2. État au moment de la rédaction

## 2.1 Déjà présent dans le runtime

Le code V3 possède déjà les fondations suivantes :

- journal SQLite/WAL immuable pour les évidences ;
- queue d’interprétation rejouable ;
- TRIPS local via KQML sur loopback ;
- conservation du message KQML natif ;
- projections sémantique et structurale partageant leurs spans ;
- registre générique des structures, relations, supports, bindings et contextes ;
- extraction incrémentale de sous-arbres structuraux ;
- propositions d’alignement par recouvrement de spans ;
- anti-unification générique et score de compression ;
- projection AtomSpace avec outbox durable ;
- ébauche de consolidation, reprocessing et génération par récupération ;
- branchement automatique du niveau 3 après la persistance d’une analyse.

Ces éléments sont une fondation, pas encore la voie inverse complète.

## 2.2 Sources locales épinglées

Inventaire actuel des sources :

```text
Cogent/TRIPS  7f80f44977f533138737c1858fd1a1e0f942acfe
disco-dop     dd181a6633e7373eed3f7049537d30e79c7ffa56
CogUtil       64dca9083dcfa485dcb70fd6fe7ba1f80e0f4082
AtomSpace     c8d633bf272b838c2132c21b7c8ddf169a18dd22
Miner         444eb6474c304775c457410592fa47a51455e36c
```

TRIPS est construit et utilisable localement. La base WordNet locale complète
est construite. Les sources disco-dop, CogUtil, AtomSpace et Miner sont
présentes, mais la chaîne disco-dop/AtomSpace/Miner doit encore être construite,
installée, sondée fonctionnellement et reliée au cycle complet.

## 2.3 Ce qui reste expressément à développer

- installateur reproductible de la pile d’apprentissage locale ;
- véritables probes fonctionnels, pas seulement détection de fichiers `.so` ;
- invocation effective de `recurringfragments` ;
- export AtomSpace déterministe et reconstruction depuis SQLite ;
- invocation effective de `cog-mine` ;
- import des résultats Miner avec provenance ;
- couplage stable entre patterns sémantiques et structuraux ;
- transfert de bindings au travers des alignements ;
- composition structurale et réalisation de surfaces nouvelles ;
- consolidation idempotente, reprise sur erreur et reprocessing planifié ;
- campagne de tests globale une fois le runtime monté.

---

# 3. Architecture d’exécution cible

```text
                       SQLite/WAL canonique
                  ┌─────────────┴─────────────┐
                  │                           │
            cycle éveillé                consolidation
                  │                           │
Evidence → TRIPS local → projections          ├─ corpus structural → disco-dop
                  │                           ├─ graphe snapshot → AtomSpace
                  ├─ observations légères     ├─ Atomese local → Miner
                  ├─ fragments bornés         ├─ anti-unification / MDL
                  ├─ alignements de spans     ├─ alignements généralisés
                  └─ contexte                 └─ nouvelles abstractions
                                                  │
                                             reprocessing
                                                  │
                                  anciennes observations / hypothèses

 cible sémantique
        │
        ├─ retrieval de patterns compatibles
        ├─ transfert de bindings par alignements
        ├─ instanciation de structures
        ├─ composition de fragments
        ├─ ranking contextuel
        └─ surface + provenance complète
```

## 3.1 Cycle éveillé

Le cycle éveillé reste peu coûteux. Après chaque analyse TRIPS persistée :

1. enregistrer les observations sémantique et structurale ;
2. enregistrer les nœuds, arêtes, spans et liens croisés ;
3. extraire un ensemble borné de fragments structuraux ;
4. créer les alignements locaux directement justifiés par les spans ;
5. enregistrer le contexte observable ;
6. créer les structures multi-tours de la fenêtre active ;
7. déposer les nouveaux objets dans l’outbox AtomSpace ;
8. proposer les révisions contextuelles séparément de l’analyse native.

Aucune recherche combinatoire lourde ne doit bloquer l’ingestion.

## 3.2 Cycle de consolidation

La consolidation travaille sur un snapshot borné et identifiable du ledger.
Elle peut être déclenchée :

- par nombre d’analyses nouvelles ;
- par temps écoulé ;
- manuellement ;
- au repos ;
- après l’arrivée d’un nouveau type d’évidence, sans coder ce type dans le
  runtime.

## 3.3 Reprocessing

Toute nouvelle abstraction acceptée produit une tâche de reprocessing. Cette
tâche recherche les anciennes observations compatibles et ajoute de nouveaux :

- matches ;
- bindings ;
- alignements ;
- scores ;
- liens de réinterprétation.

L’analyse TRIPS originelle reste intacte.

---

# 4. Modèle durable à compléter

## 4.1 `consolidation_runs`

Une exécution doit avoir un état exploitable, pas seulement une ligne finale :

```text
run_id
snapshot_watermark
algorithm
algorithm_version
parameters_json
input_ids_json
output_ids_json
status: pending | running | complete | failed
started_at
completed_at
error
environment_manifest_json
```

L’identité logique du run est dérivée du watermark, des paramètres et des
versions de code/bibliothèques. Relancer le même run ne doit pas dupliquer ses
résultats.

## 4.2 `learning_jobs`

Les opérations lourdes doivent être reprises par lease, comme
l’interprétation :

```text
job_id
kind: consolidate | mine | reprocess | graph-sync
input_id
generation
status
attempts
available_at
leased_until
lease_token
last_error
```

## 4.3 Supports et bindings

Un pattern n’est accepté que si ses supports sont traçables jusqu’aux
EvidenceUnit et AnalysisBundle. Les bindings doivent conserver :

- pattern ;
- instance ;
- variable ;
- valeur liée ;
- span éventuel ;
- alignement ayant autorisé le transfert ;
- algorithme et version.

## 4.4 Couplage des patterns

Il faut ajouter une représentation explicite d’un couple appris :

```text
CoupledPattern
  semantic_pattern_id
  structural_pattern_id
  alignment_pattern_ids
  support_set
  context_distribution
  score_components
  derivation
```

Ce couple est une donnée apprise. Il ne crée pas un nouveau type sémantique
codé dans Python.

## 4.5 Candidats de génération

Chaque candidat persistant doit contenir :

```text
candidate_id
target_fingerprint
semantic_pattern_id
structural_pattern_id
alignment_ids
fragment_ids
bindings_json
surface_text
score_components_json
support_ids_json
derivation_json
validation_json
created_at
```

---

# 5. Installation et appel des bibliothèques locales

## 5.1 Préfixes locaux

La cible est une installation contenue dans le projet :

```text
.local/opt/trips/
.local/opt/opencog/
.local/src/disco-dop-v3/
.venv/
```

L’activation doit définir seulement les chemins nécessaires :

```text
PATH
LD_LIBRARY_PATH
PYTHONPATH
GUILE_LOAD_PATH
GUILE_LOAD_COMPILED_PATH
CMAKE_PREFIX_PATH
PKG_CONFIG_PATH
```

Le script ne doit pas modifier globalement le système de l’utilisateur.

## 5.2 disco-dop

### Construction

L’installateur doit :

1. initialiser les sous-modules `cpp-btree`, `gheap` et `sparsepp` ;
2. installer Cython et les dépendances de build dans `.venv` ;
3. compiler les extensions natives ;
4. installer disco-dop en editable ou en wheel locale ;
5. exécuter un probe qui parse deux arbres et trouve au moins un fragment
   récurrent.

### Appel runtime

L’adaptateur utilisera directement l’API Python locale :

```python
from discodop.fragments import recurringfragments
from discodop.tree import Tree

trees = [Tree.parse(source, parse_leaf=int) for source in bracketed_trees]
fragments = recurringfragments(
    trees,
    sentences,
    numproc=1,
    disc=False,
    indices=True,
    maxdepth=max_depth,
)
```

Le résultat natif doit être normalisé sans perdre :

- la chaîne du fragment ;
- les indices ou comptes de support ;
- les arbres sources ;
- les phrases sources ;
- les paramètres disco-dop ;
- la version/commit de disco-dop.

L’extracteur Python incrémental actuel reste utile pour les mises à jour
légères. Il ne doit pas prétendre remplacer disco-dop lors d’une consolidation
demandant DOP.

## 5.3 AtomSpace

### Construction

La pile doit être compilée dans l’ordre imposé par ses dépendances :

```text
CogUtil → AtomSpace → Unify → URE → Miner
```

Les commits doivent être épinglés dans un manifeste. Le build doit produire :

- bibliothèques partagées locales ;
- modules Python AtomSpace si fournis par la version épinglée ;
- modules Guile/Atomese ;
- fichiers CMake nécessaires aux projets suivants.

### Projection

Le schéma AtomSpace restera technique et générique :

```text
StructureNode(id)
PatternNode(id)
EvidenceNode(id)
AnalysisNode(id)
BindingNode(id)
RelationPredicate(relation_observée)
SupportLink
DerivationLink
AlignmentLink
```

Les noms de concepts humains ne doivent pas être inventés par l’adaptateur.
Les catégories présentes dans les données peuvent être encodées comme valeurs
observées avec leur provenance.

### Synchronisation

La synchronisation suit une outbox SQLite :

1. lire les objets non synchronisés dans l’ordre ;
2. ajouter les atomes dans l’AtomSpace local ;
3. marquer la séquence comme synchronisée ;
4. conserver l’erreur et laisser l’objet rejouable en cas d’échec.

Une commande de reconstruction doit pouvoir vider uniquement la projection
éphémère en mémoire puis la rebâtir intégralement depuis SQLite.

## 5.4 OpenCog Miner

### Frontière de processus choisie

SQLite reste canonique. Pour éviter qu’un AtomSpace Python en mémoire et un
processus Guile possèdent deux états implicites différents, chaque job Miner
utilisera un snapshot Atomese déterministe exporté depuis le ledger.

Le worker local :

1. charge le snapshot dans un AtomSpace neuf ;
2. charge `(opencog miner)` ;
3. sélectionne la base d’atomes du job ;
4. appelle réellement `cog-mine` ;
5. sérialise les patterns, variables, supports et valeurs associées ;
6. retourne le résultat au processus Seman2 ;
7. Seman2 valide puis journalise ces résultats.

L’appel de principe est :

```scheme
(use-modules (opencog) (opencog miner))

(define results
  (cog-mine database
            #:minsup minimum-support
            #:max-variables maximum-variables
            #:initial-pattern initial-pattern))
```

Les noms exacts des options doivent être pris de la version locale épinglée et
validés par probe. Aucune API supposée ne doit être figée avant cette
vérification.

### Contrat de l’adaptateur Miner

Entrée :

```text
snapshot_id
database_atom_ids
minimum_support
maximum_variables
maximum_conjuncts
initial_pattern optionnel
budget temps/mémoire
```

Sortie :

```text
patterns Atomese natifs
variables
supports
valuations/bindings disponibles
scores fournis par Miner
stdout/stderr bornés
exit status
version manifest
```

La simple présence d’une bibliothèque nommée `miner` ne constitue pas une
preuve de disponibilité. Le probe exigé doit charger le module et miner un
petit graphe local connu.

## 5.5 TRIPS dans la voie inverse

TRIPS n’est pas remplacé par les bibliothèques du niveau 3. Une surface générée
peut être renvoyée au TRIPS local pour :

- vérifier qu’une analyse complète existe ;
- comparer la projection sémantique obtenue à la cible ;
- pénaliser une dérive ;
- conserver les ambiguïtés découvertes.

Cette validation est un score supplémentaire, jamais une destruction des
candidats non gagnants.

## 5.6 ERG/ACE

ERG/ACE reste un oracle grammatical hors ligne optionnel. Il peut ajouter un
signal de grammaticalité lors d’une évaluation ou d’une consolidation, mais :

- il n’est pas dans le chemin obligatoire ;
- il ne remplace pas TRIPS ;
- son absence n’active aucun service distant ;
- ses résultats sont conservés comme preuves séparées.

---

# 6. Consolidation locale détaillée

## 6.1 Ouverture d’un snapshot

Le run fixe un watermark SQLite. Seuls les objets visibles à ce watermark
participent au calcul. Cela garantit :

- reproductibilité ;
- absence de course avec l’ingestion ;
- identité déterministe des sorties ;
- comparaison de deux versions d’algorithme.

## 6.2 Préparation des corpus

Trois corpus corrélés sont produits :

1. projections sémantiques génériques ;
2. arbres structuraux indexés et séquences terminales ;
3. graphe couplé contenant supports, spans, contexte et alignements.

Leurs identifiants sources restent présents dans chaque ligne exportée.

## 6.3 Extraction structurale DOP

disco-dop cherche les fragments récurrents sur le corpus structural. Chaque
fragment accepté devient une `LearnedStructure(family="dop-fragment")` avec :

- représentation native ;
- forme canonique ;
- arbres supports ;
- profondeur et paramètres ;
- fréquence/support ;
- dérivation `disco-dop-recurringfragments`.

Les fragments lexicalisés et non lexicalisés sont conservés séparément.

## 6.4 Mining du graphe

Miner reçoit le graphe générique du snapshot. Il propose des sous-graphes
fréquents ; il ne décide pas seul qu’ils constituent des concepts utiles.

Chaque résultat Miner est d’abord enregistré comme `pattern-candidate` avec :

- Atomese natif ;
- projection JSON canonique ;
- support ;
- variables ;
- paramètres ;
- provenance du run.

## 6.5 Anti-unification

L’anti-unification complète les candidats DOP/Miner et peut généraliser des
familles d’objets partageant la même topologie observable. Elle produit :

- structure commune la plus spécifique ;
- variables techniques ;
- bindings pour chaque instance ;
- longueur descriptive indépendante ;
- longueur descriptive compressée ;
- gain de compression.

Elle doit fonctionner récursivement sur des patterns déjà appris afin de
permettre des abstractions d’abstractions.

## 6.6 Construction des patterns couplés

Les patterns sémantiques et structuraux ne sont couplés que lorsque leurs
supports permettent de le justifier. Le couplage exige :

- intersection suffisante des AnalysisBundle/Hypothesis ;
- compatibilité des spans ;
- alignements observés ou généralisés ;
- bindings cohérents sur les occurrences ;
- stabilité dans plusieurs contextes lorsque les données le permettent.

Un alignement est une relation apprise et scorée, jamais une règle Python.

## 6.7 Score d’admission

Le ranking d’un candidat combine des composantes conservées séparément :

```text
support
stabilité des bindings
gain de compression
pouvoir prédictif sur données retenues
couverture
cohérence des alignements
diversité des contextes
coût de description du pattern
qualité de provenance
```

Les poids sont des paramètres versionnés. Le score total n’efface jamais les
composantes.

## 6.8 Acceptation, fusion et scission

Les décisions possibles sont :

```text
accept candidate as pattern
retain candidate for more evidence
link candidate as specialization
link candidate as generalization
propose merge
propose split
reject for this run
```

Une fusion ou une scission crée un nouvel objet avec des liens de dérivation.
Elle ne modifie pas les anciennes lignes.

## 6.9 Fin du run

La consolidation est marquée `complete` seulement après :

1. persistance de tous les résultats ;
2. persistance des relations et supports ;
3. création des jobs de reprocessing ;
4. validation des identifiants de provenance ;
5. enregistrement du manifeste de versions.

La synchronisation AtomSpace peut rester en retard dans son outbox sans rendre
le run faux, puisque SQLite est canonique. Ce retard doit toutefois apparaître
dans le statut.

---

# 7. Reprocessing

## 7.1 Recherche des anciennes observations

Pour chaque nouveau pattern :

1. filtrer par famille et fingerprint structurel ;
2. appliquer le matcher générique ;
3. vérifier les contraintes de graphes et de spans ;
4. produire les bindings ;
5. rechercher un pattern de l’autre projection partageant les supports ;
6. proposer ou renforcer les alignements ;
7. recalculer les scores contextuels concernés.

## 7.2 Révision des hypothèses

Une révision doit indiquer :

- hypothèse originale ;
- nouvelle évidence ou nouvelle abstraction ;
- ancien score ;
- nouveau score ;
- composantes ayant changé ;
- pattern et alignement responsables ;
- version de l’algorithme.

Le reprocessing n’édite ni le KQML brut ni l’AnalysisBundle original.

## 7.3 Bornes

Le travail est borné par :

- nombre de patterns ;
- plage d’évidence ;
- temps ;
- mémoire ;
- profondeur de graphe ;
- taille des ensembles candidats.

Une interruption laisse un curseur de reprise durable.

---

# 8. Voie inverse de génération

## 8.1 Entrée

L’entrée minimale est une structure sémantique générique avec éventuellement :

- contraintes de contexte ;
- bindings déjà fixés ;
- longueur ou budget de recherche ;
- evidence/context IDs ;
- contraintes de surface observables.

Elle ne doit pas exiger une classe métier codée.

## 8.2 Étape A — normalisation de la cible

La cible est convertie dans la même représentation canonique que les
projections sémantiques apprises : nœuds, arêtes, racines, attributs et spans
disponibles. Cette opération conserve la cible brute et sa provenance.

## 8.3 Étape B — récupération des patterns sémantiques

Le moteur récupère :

- matches exacts ;
- patterns dont la cible est une instance ;
- observations proches structurellement ;
- abstractions plus générales ;
- spécialisations compatibles.

La proximité sert au ranking ; elle ne transforme pas un non-match en vérité.

## 8.4 Étape C — traversée des alignements

Pour chaque candidat sémantique, le moteur suit uniquement les alignements
appris vers :

- patterns structuraux ;
- fragments structuraux ;
- observations structurales complètes ;
- séquences de contexte compatibles.

Chaque traversée conserve le chemin exact d’identifiants.

## 8.5 Étape D — transfert des bindings

Les variables sémantiques sont liées par matching avec la cible. Elles sont
transférées vers les variables structurales lorsque les alignements appris
fournissent une correspondance justifiée :

```text
semantic variable
  → semantic node/path/span
  → learned alignment
  → structural node/path/span
  → structural variable
```

Une variable sans transfert prouvé reste libre. Elle ne reçoit pas une valeur
inventée par un handler.

## 8.6 Étape E — instanciation structurale

Les patterns structuraux sont instanciés avec les bindings transférés. Les
positions encore libres ouvrent des sites de substitution pour des fragments
DOP compatibles.

## 8.7 Étape F — composition

La composition cherche des assemblages de fragments dont :

- les frontières structurales sont compatibles ;
- les contraintes d’ordre sont satisfaites ;
- les variables partagées sont cohérentes ;
- les alignements couvrent suffisamment la cible ;
- le coût reste dans le budget.

La recherche doit être best-first ou beam-search avec budget explicite. Elle
ne doit pas parcourir sans borne toutes les combinaisons.

disco-dop fournit les fragments et leurs statistiques. Le runtime Seman2
effectue la traversée inverse et la composition ; il ne prétend pas que
`recurringfragments` est à lui seul un générateur de phrases.

## 8.8 Étape G — réalisation de la surface

Une structure complète est linéarisée à partir :

- de ses terminaux observés ;
- de l’ordre appris ;
- des réalisations lexicales portées par les fragments ;
- des bindings transférés ;
- des distributions observées pour les choix encore ambigus.

Un candidat qui nécessite une réalisation absente des données peut rester
partiel. Le runtime ne comble pas le trou avec un template manuel.

## 8.9 Étape H — validation locale

Les surfaces complètes peuvent être réanalysées par TRIPS local. On compare :

- couverture de la cible ;
- compatibilité du graphe réanalysé ;
- ambiguïtés supplémentaires ;
- complétude structurale ;
- éventuel signal ERG/ACE hors ligne.

Les messages natifs de validation sont stockés comme nouvelles dérivations,
pas comme évidence utilisateur.

## 8.10 Étape I — ranking

Les composantes prévues sont :

```text
compatibilité cible/pattern sémantique
couverture de la cible
support du pattern couplé
probabilité/coût des fragments
cohérence des bindings
compatibilité contextuelle
score de validation TRIPS
signal grammatical optionnel
gain de compression
poids de provenance
coût de recherche
```

Plusieurs candidats sont retournés avec leurs scores détaillés. Le runtime ne
masque pas l’ambiguïté en ne conservant que le premier.

## 8.11 Modes de génération

Trois modes graduels utilisent la même architecture :

1. **récupération** — réutiliser une réalisation observée compatible ;
2. **instanciation** — remplacer des bindings dans un pattern structural appris ;
3. **composition** — assembler plusieurs fragments alignés.

Le premier mode sert de baseline et de fallback local traçable. Le troisième
est la cible permettant des surfaces réellement nouvelles.

---

# 9. API à exposer

## 9.1 Runtime Python

```python
runtime.consolidate(
    minimum_support=2,
    use_discodop=True,
    use_miner=True,
    budget=None,
)

runtime.reprocess(
    pattern_ids=None,
    evidence_range=None,
    budget=None,
)

runtime.generate(
    target,
    context=None,
    bindings=None,
    modes=("retrieve", "instantiate", "compose"),
    limit=10,
    budget=None,
)

runtime.model_trace(structure_id)
runtime.rebuild_atomspace()
runtime.learning_status()
```

## 9.2 CLI

```text
seman2 consolidate
seman2 reprocess
seman2 generate TARGET_JSON
seman2 model-trace STRUCTURE_ID
seman2 rebuild-atomspace
seman2 status
seman2 awake
```

Toutes les commandes doivent afficher :

- identifiants de run/job ;
- versions locales utilisées ;
- compte des entrées/sorties ;
- indisponibilités explicites ;
- erreurs rejouables ;
- retard éventuel des outboxes.

---

# 10. Gestion des erreurs et observabilité

## 10.1 Séparation des étages

Une analyse TRIPS déjà persistée ne doit jamais repasser à `failed` parce que :

- disco-dop échoue ;
- AtomSpace ne charge pas ;
- Miner dépasse son budget ;
- une consolidation est interrompue.

Ces échecs appartiennent à des jobs de niveau 3 distincts.

## 10.2 Sorties natives

Pour chaque appel externe local, conserver de façon bornée :

- commande ou fonction appelée ;
- paramètres ;
- code de retour ;
- stdout ;
- stderr ;
- durée ;
- empreinte des entrées ;
- manifeste logiciel.

## 10.3 Probes fonctionnels

Le statut `available` exige un probe réussi :

- TRIPS : échange KQML local et analyse ;
- disco-dop : extraction d’un fragment récurrent ;
- AtomSpace : création puis lecture d’un petit sous-graphe ;
- Miner : résultat de `cog-mine` sur un graphe minimal ;
- ERG/ACE : analyse locale si configuré.

---

# 11. Ordre de développement

## Phase A — rendre les dépendances locales reproductibles

1. ajouter `scripts/install_learning_stack.sh` ;
2. épingler les commits et sous-modules ;
3. construire disco-dop dans `.venv` ;
4. construire CogUtil, AtomSpace, Unify, URE et Miner sous `.local/opt/opencog` ;
5. compléter `activate_local.sh` ;
6. ajouter les probes fonctionnels et le manifeste.

## Phase B — rendre la consolidation transactionnelle

1. ajouter jobs, leases, watermark et états de run ;
2. séparer observation légère et consolidation lourde ;
3. rendre les identités de résultats déterministes ;
4. implémenter reprise et budgets ;
5. finaliser l’extraction disco-dop réelle.

## Phase C — intégrer AtomSpace et Miner réellement

1. finaliser le mapping générique SQLite → Atomese ;
2. implémenter reconstruction AtomSpace ;
3. exporter un snapshot déterministe ;
4. appeler `cog-mine` dans un worker local ;
5. réimporter patterns, supports et bindings ;
6. supprimer la détection superficielle par nom de bibliothèque.

## Phase D — construire le modèle couplé

1. généraliser séparément sémantique et structure ;
2. généraliser les alignements ;
3. construire `CoupledPattern` à partir des supports communs ;
4. calculer les scores d’admission ;
5. permettre abstractions d’abstractions ;
6. programmer le reprocessing.

## Phase E — compléter la voie inverse

1. matching cible/pattern ;
2. traversée des alignements ;
3. transfert de bindings ;
4. instanciation structurale ;
5. recherche et composition de fragments ;
6. linéarisation ;
7. validation TRIPS locale ;
8. ranking multi-facteurs ;
9. persistance et trace de tous les candidats.

## Phase F — cycle continu et exploitation

1. terminer `awake` avec scheduler et budgets ;
2. exposer statut et backlog ;
3. rendre consolidation et reprocessing interrompables ;
4. documenter les commandes opératoires ;
5. seulement ensuite lancer la campagne de tests globale demandée.

---

# 12. Critères d’acceptation futurs

La fonctionnalité sera considérée complète lorsque :

1. toutes les bibliothèques requises sont locales et leurs probes passent ;
2. le runtime continue d’ingérer pendant une consolidation ;
3. un run identique est idempotent ;
4. un arrêt forcé peut reprendre sans perte ni duplication logique ;
5. disco-dop produit des fragments avec leurs supports réels ;
6. Miner est effectivement invoqué et ses sorties sont réimportées ;
7. AtomSpace peut être reconstruit entièrement depuis SQLite ;
8. une abstraction nouvelle peut reclassifier des observations anciennes sans
   modifier les analyses natives ;
9. la génération retourne plusieurs candidats avec trace complète ;
10. au moins un candidat nouveau est obtenu par instanciation ou composition,
    et non par simple copie d’une phrase observée ;
11. chaque portion de surface produite remonte à un fragment, un binding ou une
    observation ;
12. aucune catégorie métier et aucun template de phrase n’ont été ajoutés au
    runtime ;
13. une recherche dans le code ne révèle aucun endpoint TRIPS distant ni
    fallback réseau ;
14. le rejeu depuis l’évidence brute reconstruit les projections et le modèle
    appris de manière déterministe sous le même manifeste logiciel.

---

# 13. Hors périmètre de cette étape

- interface graphique ;
- service distribué ;
- cluster AtomSpace ;
- entraînement neuronal ;
- ontologie métier manuelle ;
- templates de dialogue ;
- promotion d’ERG en parser principal ;
- optimisation prématurée avant la validation de la voie complète.

La priorité reste : une boucle locale complète, traçable et rejouable, même si
elle est d’abord lente sur un petit corpus.
