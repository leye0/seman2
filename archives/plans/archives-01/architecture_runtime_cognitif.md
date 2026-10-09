# Architecture d'exécution du système cognitif NLP

Ce document transforme l'architecture conceptuelle et les capacités vérifiées
par les POC en une architecture exécutable. Il ne remplace pas
`architecture_systeme_cognitif_symbolique.md`, qui demeure la spécification
scientifique et cognitive. Il définit comment faire fonctionner ses systèmes
ensemble sans transformer le corpus en base de réponses et sans introduire un
LLM dans le chemin cognitif.

La description machine correspondante est
`plans/cognitive_system_architecture.json`.

## 1. Produit et invariants fondamentaux

Le produit est un chatbot cognitif symbolique apprenant, non-LLM. Deux modes
partagent un même cœur, les mêmes structures et les mêmes mémoires :

- **ingestion** : transformer un flux d'expériences provenant des corpus en
  structures et connaissances de plus en plus abstraites;
- **chatbot** : traiter une observation utilisateur avec ce même cœur, activer
  les connaissances apprises, raisonner, planifier et produire un nouveau tour.

Les invariants sont les suivants :

1. Une couche haute ne lit jamais directement les Parquet ni une annotation
   d'évaluation. Elle consomme des artefacts produits par les couches sous elle.
2. Les relations natives de la source — ordre, auteur, parent de thread,
   timestamp, bloc de code — sont des observations de source, pas des concepts
   cognitifs déjà compris.
3. Une sortie externe est conservée dans son formalisme natif et attribuée à
   son producteur. Les adaptateurs ajoutent des projections; ils ne remplacent
   jamais la valeur native.
4. Une analyse absente ou en échec reste une information explicite. Aucun
   composant ne fabrique une sortie de remplacement pour compléter le flow.
5. Les hypothèses, justifications, contradictions et sélections restent
   distinctes. Une sélection historique ne réécrit jamais le passé.
6. Le runtime vivant est principalement en RAM. La persistance sert aux
   checkpoints, au journal de reprise et, sous pression mémoire, au stockage
   froid réversible; elle n'est pas le cerveau actif.
7. Les seuils cognitifs sont des données du Control State et de la mémoire de
   travail. Des limites de sûreté non modifiables empêchent néanmoins un module
   de faire tomber la machine.
8. OpenRouter et les labels de corpus appartiennent uniquement au plan
   d'évaluation. Ils ne peuvent modifier ni une mémoire cognitive, ni un score,
   ni une décision Soar.

## 2. Topologie de déploiement

Un « service » désigne une responsabilité logique avec un contrat, une mémoire
et un cycle de vie. Il ne signifie pas nécessairement un microservice réseau.
Le déploiement initial comprend :

```text
┌──────────────────────────────────────────────────────────────────────┐
│                     COGNITIVE RUNTIME PROCESS                        │
│                                                                      │
│  scheduler │ artifact arena │ graph memories │ indexes │ Soar       │
│  control state │ hypothesis store │ episodes │ induction            │
└───────────────┬───────────────────────────────────────┬──────────────┘
                │ typed jobs                            │ checkpoints
                ▼                                       ▼
┌──────────────────────────────┐              ┌───────────────────────┐
│ ISOLATED ANALYZER WORKERS    │              │ PERSISTENCE PROCESS   │
│ ACE/ERG, DS, RST, temporal,  │              │ journal + atomic      │
│ code, phonology, NLG         │              │ snapshots + cold data │
└──────────────────────────────┘              └───────────────────────┘
```

Les structures actives restent dans un **Artifact Arena** partagé en mémoire.
Les analyseurs externes lourds ou fragiles vivent dans des workers isolés avec
files bornées, timeouts, limites de threads et redémarrage indépendant. Le
runtime échange des identifiants et charges typées, pas les répertoires de
sortie des POC.

Cette topologie évite à la fois :

- un monolithe où un parseur peut faire tomber toutes les mémoires;
- une constellation de microservices qui sérialise le graphe à chaque arête;
- une base de données utilisée comme bus cognitif principal.

## 3. Contrat universel de matière

Tout système publie un `CognitiveArtifact` immuable :

```text
artifact_id
artifact_type
schema_id
producer_id
producer_build
configuration_digest
mode                         ingestion | chatbot
session_id                   corpus session ou conversation
observation_refs             zéro, une ou plusieurs observations causales
episode_refs                 zéro, un ou plusieurs épisodes causaux
wave                         vague de propagation
derivation_depth
source_anchors               offsets, tokens, segments, objets source
parent_ids
payload_native               sortie originale si producteur externe
payload_projection           projections ajoutées par nos adaptateurs
status                       success | partial | failure | unknown
justification_ids
contradiction_ids
losses
created_sequence
```

Il n'existe pas de champ universel `truth_score`. Un composant peut publier une
mesure propre et documentée, mais le support épistémique reste un objet composé
de preuves, contradictions, provenance, contraintes et histoire de sélection.

Les artefacts sont append-only. Une révision produit un nouvel artefact qui
référence l'ancien. Les graphes vivants peuvent exposer des vues mutables et
indexées, mais leur journal causal reste immuable.

## 4. Scheduler à propagation bornée

Le scheduler est événementiel et orienté types. Chaque module déclare :

- les types qu'il consomme;
- les types qu'il produit;
- les préconditions minimales et optionnelles;
- sa politique de déclenchement sur entrée partielle;
- son coût estimé;
- sa mémoire propriétaire;
- son codec de checkpoint;
- les métriques de pression et de progrès.

Une observation ouvre une **propagation wave**. Les analyseurs indépendants
partent en parallèle. Leurs sorties déclenchent les intégrateurs puis les
systèmes plus abstraits. Un feedback provenant de l'induction, du contexte ou
d'une sélection ne peut affecter que la vague suivante. Cette règle empêche les
cycles instantanés et rend le replay déterministe.

Une vague se termine lorsque :

- aucune tâche prête ne reste;
- tous les travaux requis sont terminés, en échec ou expirés;
- aucune nouvelle matière ne franchit les seuils de propagation;
- ou la profondeur/budget maximal est atteint.

Le système peut produire une structure partielle avant que tous les analyseurs
aient répondu. L'arrivée tardive d'une analyse ouvre une révision attribuée au
lieu de modifier silencieusement l'interprétation existante.

## 5. Control State et mémoire de travail

Le `Control State` est une structure cognitive vivante, visible et modifiable
par les règles de contrôle autorisées. Il contient notamment :

| Paramètre | Fonction |
|---|---|
| `max_derivation_depth` | profondeur maximale d'abstraction pour la vague; |
| `activation_floor` | seuil minimal pour maintenir un objet dans le contexte actif; |
| `hypothesis_beam_width` | nombre maximal d'interprétations matérialisées; |
| `novelty_reserve` | places réservées aux alternatives structurellement différentes; |
| `max_active_entities` | taille de la projection de situation active; |
| `retrieval_budget` | nombre/coût des recherches structurelles; |
| `per_module_work_budget` | budget de calcul par module et par vague; |
| `induction_trigger` | support, récurrence ou pression déclenchant l'induction; |
| `consolidation_pressure` | seuil de déplacement vers mémoire froide; |
| `decay_policy` | décroissance d'activation, jamais effacement implicite; |
| `repair_budget` | profondeur des réparations et clarifications online; |

Soar manipule les buts, sous-buts, opérateurs, impasses et certains paramètres
du Control State. Des **Safety Limits** extérieures à Soar imposent les maxima
physiques : RAM, nombre de workers, taille de batch, timeout et espace de
checkpoint. Soar peut choisir dans l'enveloppe sûre, pas la dépasser.

Le filtrage cognitif se fait après production de matière, à chaque étage :

```text
matière publiée
    ├── active : continue immédiatement vers les couches supérieures
    ├── latent : reste en mémoire et peut être réactivée
    ├── cold   : sérialisée avec pointeur reconstructible
    └── rejected hypothesis : conservée avec la raison du rejet
```

Cela est distinct du batch d'entrée, qui protège seulement les ressources I/O.

## 6. Couches et systèmes

Les couches indiquent une dépendance de matière, pas une taxonomie cognitive
figée. Plusieurs systèmes d'une couche travaillent en parallèle et une sortie
peut nourrir plusieurs couches ultérieures.

### L0 — Adaptateurs d'expérience

- `corpus-ingestion` lit les Parquet par fragments bornés, maintient les
  curseurs et restitue l'ordre des documents et conversations;
- le roman textuel et le dictionnaire JSONL empruntent exactement la même
  frontière. Une entrée de dictionnaire est une expérience structurée à lire :
  son mot vedette, sa catégorie déclarée, ses définitions et ses exemples sont
  des données source, jamais des primitives sémantiques déjà acquises;
- `interaction-ingestion` reçoit les tours utilisateur, métadonnées de canal et
  signaux disponibles;
- `curriculum-controller` choisit la complexité des observations d'entraînement
  sans utiliser leur réponse comme cible cognitive;
- `source-graph` conserve documents, auteurs, threads, relations natives,
  timestamps, blocs de code, citations et éditions.

Sortie : `source-event`, `source-segment`, `source-relation`.

### L1 — Observation et provenance

- segmentation et unités observables;
- ancres caractère/token/segment;
- Observation Graph immuable;
- Transmission / Provenance Graph;
- séparation contenu, porteur, auteur, citation et chaîne de transmission.

Sortie : `observation`, `observable-unit`, `transmission-event`,
`source-anchor`.

### L2 — Analyses formelles parallèles

À partir des observations, le dispatcher lance selon la modalité :

- **ERG/ACE** : HPSG, arbres, dérivations, MRS, EDS et DMRS;
- **Link Grammar** : linkages syntaxiques concurrents;
- **Dynamic Syntax** : états incrémentaux et TTR natif disponible;
- **lexical resources** : WordNet, VerbNet, PropBank, FrameNet, SemLink et SUMO,
  toujours reliés à une occurrence précise;
- **form/phonology** : Epitran, PanPhon, G2P, WFST/OpenFst/Pynini et candidats
  concurrents;
- **code** : Tree-sitter, erreurs et fragments incomplets;
- **temporal surface** : HeidelTime/Duckling en quarantaine comme annotations de
  surface, jamais comme modèle temporel interne;
- **discourse parsers** : sorties RST/eRST natives lorsqu'une unité suffisante
  est disponible.

Sortie : `native-analysis` ou `analysis-failure`, sans fusion.

### L3 — Adaptation et liaison cross-représentation

- adaptateurs vers des fragments de graphe attribués;
- conservation des valeurs natives et des pertes;
- liens occurrence → ressource;
- correspondances ERG/Link Grammar/Dynamic Syntax;
- correspondances orthographie/phonologie/symboles/sens;
- alignements texte/code/discours;
- résolution locale de contraintes;
- candidats d'identité, jamais identité implicite.

Sortie : `graph-fragment`, `alignment-candidate`, `constraint-set`,
`cross-representation-hypothesis`.

### L4 — Sémantique, référence et temporalité relationnelle

- composition sémantique et portée;
- entités particulières, références et coréférences candidates;
- prédicats, rôles, propriétés, états et événements;
- ordre observable séparé des interprétations;
- algèbre d'Allen et propagation de contraintes;
- E/R/S de Reichenbach;
- aspect, persistance et relations temporelles discursives;
- anaphores temporelles et contexte épisodique;
- coordonnées calendaires externes conservées comme ancres séparées.

Sortie : `semantic-structure`, `entity-candidate`, `event-candidate`,
`temporal-constraint-network`, `state-update-candidate`.

### L5 — Hypothèses factorisées

Le gestionnaire d'hypothèses reçoit toutes les familles précédentes sans
former leur produit cartésien :

- alternatives persistantes par famille;
- justifications, contradictions et nogoods;
- Evidence Ledger contextuel;
- révision non destructive;
- composition paresseuse;
- partage structurel et déduplication;
- beam actif borné avec réserve de diversité;
- pruning réversible et stockage froid.

Sortie : `hypothesis-family`, `lazy-composition`, `active-beam`,
`selection-history`.

### L6 — Tour, discours et dialogue

- structure RST/eRST et graphe SDRT;
- fonctions communicatives ISO 24617-2/DiAML;
- KoS/TTR et Dialogue Gameboard;
- candidats Information State Update;
- grounding et degrés d'établissement;
- QUD, fragments et ellipses;
- réparations, clarifications et corrections;
- obligations discursives;
- référence inter-tours et relations aux locuteurs;
- baselines ConvoKit/OpenDial encapsulées, jamais autoritaires.

Ces systèmes consomment les artefacts L1–L5. Un `native_type=answer` provenant
de Stack Overflow reste un fait source; la relation sémantique « répond à » est
une hypothèse discursive produite ici.

Sortie : `discourse-relation-candidate`, `dialogue-act-candidate`,
`qud-state-candidate`, `grounding-update`, `discourse-obligation`,
`dialogue-state-update-candidate`.

### L7 — Situation, épisodes et mémoires vivantes

- projection de situation/world state par deltas réversibles;
- état interactionnel courant;
- épisodes avec ordre, provenance, hypothèses et choix historiques;
- mémoire épisodique relationnelle;
- mémoires propriétaires des systèmes de dialogue et de discours;
- indexes de recherche structurelle exacte, partielle et séquentielle.

Sortie : `situation-delta`, `situation-snapshot`, `episode`,
`memory-index-update`.

### L8 — Statistiques, induction et concepts appris

- statistiques de support et récurrence;
- motifs de sous-graphes;
- transformations récurrentes;
- Formal Concept Analysis;
- Inductive Logic Programming;
- promotion, merge, split et oubli explicable;
- induction récursive et compression hiérarchique;
- acquisition de relations sémiotiques;
- concepts, scripts, attentes et régularités discursives;
- structures culturelles, relations de groupes et familles d'humour apprises;
- révision lorsqu'une interprétation culturelle échoue.

Les structures induites référencent toujours leurs occurrences et preuves. Une
structure promue devient une nouvelle sorte de matière consommable par les
étages L4–L8 lors d'une vague ultérieure; elle n'altère jamais les observations
qui l'ont produite.

Sortie : `statistical-summary`, `pattern-candidate`, `learned-relation`,
`learned-concept`, `learned-script`, `learned-transformation`.

### L9 — Contrôle cognitif et retrieval

- recherche exacte, partielle, cross-représentation et séquentielle;
- activation d'un sous-graphe pertinent;
- construction du Grand Contexte Global borné;
- working memory Soar;
- buts, sous-buts, opérateurs, préférences et impasses;
- accès aux mémoires sémantique et épisodique Soar;
- chunking et mémoire procédurale;
- réglage dynamique des seuils dans les limites de sûreté.

Soar ne contient ni tout le corpus ni tout le Learned Graph. Il reçoit des
références et projections actives, peut demander d'autres éléments aux
mémoires internes et produit des décisions attribuées.

### L10 — Action conversationnelle

En mode chatbot seulement :

- génération de transformations d'état candidates;
- sélection d'une transformation par contraintes et opérateurs;
- plan communicatif inspectable : but, contenu, ordre, référence, initiative;
- réalisation via SimpleNLG ou autre réalisateur attribué;
- candidats multiples de surface;
- observation de la production propre du système;
- apprentissage ultérieur des régularités de réalisation.

Sortie : `selected-transformation`, `communicative-plan`,
`surface-candidate`, `system-utterance`.

## 7. Flow du mode ingestion

```text
1. corpus-ingestion lit un petit batch physique depuis un corpus Parquet,
   textuel ou JSONL
2. source-graph et observation-graph publient les observations ordonnées
3. le scheduler lance en parallèle les analyses L2 applicables
4. les adaptateurs L3 publient fragments, correspondances et échecs
5. L4 construit matière sémantique, référentielle et temporelle
6. L5 maintient les familles d'hypothèses sans explosion combinatoire
7. L6 construit les structures discursives et dialogue sur plusieurs tours
8. L7 applique les deltas sélectionnés et ferme les épisodes à quiescence
9. L8 met à jour statistiques, motifs, concepts, scripts et culture apprise
10. les nouvelles structures apprises deviennent disponibles à la vague suivante
11. le curseur avance seulement après le watermark de commit/checkpoint requis
```

Le curriculum commence par des observations réellement traitables : tours
courts, syntaxe simple, réponse directe et peu de code. La difficulté augmente
selon des mesures observées — longueur, profondeur syntaxique, ambiguïté,
nombre de tours, code, références et échecs — et non selon une prétendue
compréhension déjà fournie par les labels.

Les cas Stack Overflow complexes actuellement utilisés restent des stress tests
de couverture. Ils ne constituent pas le premier curriculum end-to-end.

## 8. Flow du mode chatbot

```text
1. interaction-ingestion publie le tour utilisateur
2. L1–L6 exécutent le même traitement bottom-up que l'ingestion
3. L7 projette les deltas possibles dans la situation active
4. L9 récupère épisodes, concepts, scripts et preuves pertinents
5. Soar choisit interprétation, retrieval supplémentaire ou réparation
6. L10 produit des transformations candidates puis un plan communicatif
7. le réalisateur produit plusieurs surfaces attribuées
8. Soar sélectionne/autorise la sortie dans les limites du plan
9. la sortie est enregistrée comme observation propre du système
10. l'épisode et les mémoires vivantes sont mis à jour
```

Le mode chatbot peut continuer à apprendre. Une politique explicite décide
quels événements online participent à l'induction et lesquels restent dans une
mémoire de session.

## 9. Mémoires

| Domaine | Autorité pendant l'exécution | Contenu |
|---|---|---|
| Source/Observation | RAM + journal | événements immuables et ancres; |
| Analyses natives | RAM, cold spill permis | sorties attribuées et échecs; |
| Hypothèses | RAM avec partage structurel | familles, preuves, nogoods, sélections; |
| Situation | RAM | deltas et projection active; |
| Dialogue/Discours | RAM | QUD, grounding, obligations, SDRT, gameboard; |
| Épisodique | RAM indexée | épisodes et liens temporels; |
| Learned Graph | RAM indexée | relations, concepts, scripts et transformations; |
| Soar WM | RAM Soar, strictement bornée | contexte actif et contrôle; |
| Soar SM/EM/PM | mémoires natives + miroir attribué | éléments appris par Soar; |
| Cold Store | disque | objets latents reconstructibles; |
| Checkpoint | disque atomique | image coordonnée de toutes les mémoires; |

Le stockage froid n'est jamais une poubelle : chaque objet déplacé conserve son
identité, ses indexes minimaux et sa procédure de reconstruction.

## 10. Checkpoint et reprise

Une barrière d'arrêt :

1. suspend les nouvelles lectures et entrées;
2. termine ou journalise les jobs externes en vol;
3. stabilise la vague et son watermark;
4. sérialise chaque mémoire propriétaire;
5. sauvegarde artefacts, graphes, indexes et activation;
6. sauvegarde Control State et files du scheduler;
7. sauvegarde agent, mémoires natives et contexte reconstructible Soar;
8. sauvegarde curseurs de corpus, sessions et générateurs pseudo-aléatoires;
9. écrit les empreintes dans un manifeste atomique.

La reprise reconstruit tout cela avant de rouvrir l'ingestion ou le canal
chatbot. Une simple base SQLite ou un `save agent` Soar ne constitue pas, seul,
un checkpoint cognitif.

## 11. Couverture des POC

La description machine associe chaque famille de services aux POC qui ont
validé ses outils ou invariants. Cette association signifie « capacité
disponible », pas « POC utilisée comme dépendance runtime ».

| Famille | POC principales |
|---|---|
| grammaires et sémantique profonde | NLP-01…06 |
| lexiques et alignement d'occurrences | LEX-01…07 |
| temporalité relationnelle | TIME-01…08 |
| forme, phonologie et acquisition sémiotique | SEM-01…06 |
| discours | DISC-01…02 |
| dialogue formel et pragmatique | DLG-01…14 |
| culture apprise | CULT-01…06 |
| code | CODE-01…02 |
| contrats de graphes | GRAPH-01…03 |
| incertitude et hypothèses | HYP-01…08 |
| retrieval | RET-01…04 |
| statistiques et contraintes | STAT-01, CONS-01 |
| induction | IND-01…06 |
| contrôle Soar | SOAR-01…05 |
| planification et génération | COMM-01…03, GEN-01…04 |
| propriétés systémiques | RUN-01…04, X-01…07 |

RUN-03 et RUN-04 ont été réimplémentées sur cette architecture. RUN-03 ingère
la question et la réponse humaine comme deux observations successives et
compare l'exécution continue à une reprise sur checkpoint. RUN-04 construit
ses transformations depuis les artefacts émergents, les soumet à un vrai agent
Soar et vérifie qu'aucun choix par défaut n'apparaît lorsqu'aucun opérateur
n'est admissible. Aucune des deux POC ne consulte le corpus depuis le retrieval
cognitif.

SEM-03 à SEM-06 possèdent également une tranche intégrée exécutable. Les
relations de forme pondérées et les candidats G2P sont des analyses externes
attribuées; SEM-05 les conserve dans des plans de retrieval indépendants;
SEM-06 consomme ces plans avec les invariants IND/HYP et apprend une relation
conditionnelle anonyme au fil d'épisodes immuables. Ces POC valident les
contrats et la causalité de cette branche; elles ne signifient pas encore que
Pynini et Phonetisaurus sont activés dans la commande générale d'ingestion.

## 12. Découpage d'implémentation

L'ordre d'implémentation suit la matière, pas le niveau spectaculaire du POC :

1. **Implémenté et testé** — contrats `CognitiveArtifact`, registre de types et
   Artifact Arena en RAM;
2. **Implémenté et testé** — scheduler, Control State, budgets, vagues,
   feedback différé et reprise déterministe;
3. **Fondation implémentée** — ingestion textuelle, dictionnaire JSONL et
   ingestion Parquet séquentielle, `Source → Observation` et provenance causale.
   Le texte léger
   `data/the_map_of_everything_nlp_novel.txt` sert au test rapide; le véritable
   échantillon StackOverflow vérifie aussi la frontière sans faire entrer les
   votes ni labels dans l'Artifact Arena. Les définitions du dictionnaire
   traversent le même chemin et ne créent directement aucun sens interne;
4. **Verticale textuelle implémentée et testée** — segmentation, routage
   explicite puis workers isolés ACE/ERG, Link Grammar, Dynamic Syntax,
   WordNet/VerbNet/PropBank/FrameNet/SemLink/SUMO et
   Epitran/PanPhon/CMUdict. Les frontières parallèles sont limitées à quatre
   workers et leurs publications restent déterministes. Tree-sitter est routé
   seulement pour une observation explicitement typée `code`. RST et les
   normaliseurs calendaires ne sont pas exécutés lorsqu'un contrat requis
   manque; le motif de non-applicabilité est un artefact, pas un silence;
5. **Ledger et liens inter-représentations implémentés** — sorties natives et
   échecs sont conservés séparément; formes, spans lexicaux, tokens Link Grammar
   et relations MRS sont alignés comme hypothèses sans identité forcée. Toute
   structure sémantique porte ce bundle comme parent causal;
6. **Sémantique, référence et temps implémentés pour la verticale** — MRS vers
   graphe et structure sémantique, continuité de mentions entre observations,
   réseaux E/R/S et résolution de cohérence réelle par Z3. Les coordonnées
   absolues inconnues restent absentes;
7. **Hypothèses, Soar, discours et dialogue implémentés pour l'ingestion** — les lectures
   sont factorisées par unité, projetées dans une mémoire de travail Soar
   bornée, puis reliées à l'ordre discursif observé. Les forces de phrase MRS
   alimentent des actes de dialogue, QUD et grounding candidats sans relire le
   texte brut. Soar maintient les alternatives et ne choisit pas une vérité;
8. **Mémoire montante implémentée** — branches de situation réversibles,
   épisodes non affirmés, index de retrieval interne et statistiques par
   épisode. Les alternatives d'une même observation ne gonflent pas le support;
9. **Induction, apprentissage culturel et transformations fonctionnels** — les motifs
   récurrents proviennent exclusivement des épisodes. Au seuil de promotion,
   le système crée des candidats anonymes traçables; il ne leur assigne ni sens
   culturel ni vérité automatiquement. Des transformations mémoire concurrentes
   sont ensuite construites sur cette matière et arbitrées par Soar sans
   engagement de vérité;
10. **Exécution suspendable implémentée** — curseur source, runtime RAM,
    scheduler et Control State sont checkpointés atomiquement. Après quiescence,
    la pression de mémoire rétrograde l'ancien matériau en `latent` sans le
    supprimer;
11. **Commande d'intégration** — `./scripts/seman2 cognitive-system-ingest`
    exécute cette verticale sur le roman ou le dictionnaire et rapporte les
    modules réellement participants. Son GO exige les 28 modules applicables,
    les branches formelles obligatoires, Z3, les deux contrôles Soar, le dialogue
    et une consolidation sans engagement de vérité. Le test couvre aussi
    arrêt/reprise et le routage Tree-sitter;
12. **Hors de cette verticale d'ingestion textuelle** — RST sur span multi-EDU,
    ancrage Duckling/HeidelTime avec calendrier attribué, ingestion mixte de
    blocs de code depuis les Parquet et les systèmes de réponse du mode chatbot
    conservent leurs contrats dédiés et ne sont pas simulés sur une phrase qui
    ne les rend pas applicables.

À chaque étape, une POC d'intégration doit comparer les artefacts produits à ce
qui est réellement attendu pour l'observation, sans fournir cette attente au
runtime.

Le socle vit dans `seman2_runtime/cognitive_artifacts.py`,
`control_state.py`, `cognitive_scheduler.py`, `cognitive_runtime.py`,
`cognitive_ingestion.py` et `cognitive_formal_analysis.py`. Les tests couvrent
le fan-out parallèle, la causalité complète jusqu'à l'état culturel, le refus
d'un raccourci `Source → high level`, la pression de mémoire, le feedback à
vague suivante, le routage par modalité et la reprise déterministe.
