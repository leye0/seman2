# Architecture cognitive développementale de seman2

## Statut du document

Ce document définit la nouvelle cible architecturale de seman2.

Il repart du produit recherché plutôt que de la succession actuelle des POC.
Les anciens documents restent utiles pour leurs inventaires, leurs résultats
expérimentaux et leurs contraintes techniques, mais ils ne doivent pas être
interprétés comme la preuve que le cœur cognitif décrit ici existe déjà.
Ils sont répertoriés dans `plans/archives/README.md`.

Le code et les POC antérieurs sont archivés ou considérés comme candidats. Ils
ne sont réintroduits que lorsqu'une preuve verticale dérivée de cette
architecture démontre leur rôle sur de la matière réellement produite par les
étages inférieurs. Une capacité locale n'est jamais transformée en capacité
cognitive globale par simple assemblage.

---

## 1. Produit recherché

Seman2 est un apprenant cognitif symbolique et développemental destiné à
devenir un agent conversationnel non-LLM.

Il possède deux modes qui utilisent exactement le même état cognitif :

- **ingestion** : vivre des expériences linguistiques ordonnées, construire des
  formes, des épisodes, des relations, des attentes et des concepts;
- **chatbot** : comprendre un nouveau tour avec les mêmes mécanismes, mobiliser
  seulement les connaissances effectivement acquises, raisonner, répondre et
  apprendre éventuellement de l'interaction.

Un modèle seman2 n'est pas supposé disposer d'une culture générale universelle.
Il est défini par une architecture commune et par une trajectoire particulière
d'expériences. Deux modèles exposés à des vies linguistiques différentes doivent
pouvoir développer des connaissances, des attentes et des manières de parler
différentes sans recevoir un personnage sous forme de prompt.

Un modèle doit notamment pouvoir dire qu'il ignore quelque chose. Une absence
de connaissance ne doit jamais être comblée par une ressource cachée, un corpus
interrogé au moment de répondre ou un LLM externe.

Le premier système apprend à partir d'expériences linguistiques et
interactionnelles. Il ne prétend pas posséder une perception visuelle, motrice
ou corporelle qu'il n'a pas. Le contrat `ExperienceOccurrence` reste néanmoins
ouvert à d'autres modalités afin qu'une extension ultérieure puisse ajouter de
nouvelles formes d'expérience sans remplacer les mémoires et concepts déjà
définis.

### 1.1 Décisions normatives

Les décisions suivantes structurent toute l'architecture :

1. **Double représentation** — formes distribuées superposées et structures
   relationnelles formelles sont toutes deux indispensables et réversiblement
   reliées.
2. **Compétence grammaticale forte au départ** — le modèle commence avec les
   mécanismes grammaticaux low level et high level; il apprend le contenu, pas
   la grammaire depuis zéro.
3. **Représentations potentielles innées, contenu acquis** — le noyau fournit
   des espaces pour identité, rôles, contexte, événements, états, temps,
   discours et dialogue, sans fournir les faits particuliers du monde.
4. **Construction conceptuelle totale** — toute analyse pertinente peut
   contribuer à la forme; aucune analyse unique ne devient le sens final.
5. **Récursion conceptuelle** — une structure apprise peut redevenir un facteur,
   un référent ou un participant d'une abstraction supérieure.
6. **Aucune banque sémantique initiale parallèle** — les banques lexicales et
   verbales externes ne sont ni une mémoire du modèle, ni un système de réponse.
7. **Vocabulaire ouvert** — formes inconnues, fautes, slang, emprunts et usages
   artistiques restent traitables sous hypothèses concurrentes.
8. **Temps relationnel** — les normalisateurs de surface ne définissent pas le
   temps cognitif.
9. **Soar comme noyau exécutif** — Soar porte le foyer de travail et contrôle les
   actions mentales; il ne contient pas l'univers conceptuel complet.
10. **Attention graduelle** — périphérie active, contexte de situation, mémoire
    intermédiaire et mémoire longue restent distincts du foyer Soar.
11. **Retrieval piloté par un but** — la profondeur s'élargit progressivement et
    reste bornée; les associations lointaines n'entrent pas automatiquement dans
    la working memory.
12. **Oubli cognitif réel** — le journal scientifique externe ne sert jamais de
    RAG ni de mémoire parfaite au chatbot.
13. **Curriculum évalué sur critères préétablis** — le LLM externe juge certains
    comportements; il ne produit aucune décision cognitive ni connaissance.
14. **Admission conditionnelle des outils** — un outil installé ou validé en POC
    peut être quarantainé ou retiré si sa contribution nette n'est pas démontrée.

---

## 2. Thèse architecturale

Le cœur du système n'est ni un pipeline de parsing, ni une base de triplets, ni
un graphe statique, ni un vecteur dense opaque.

Le cœur est un ensemble de mémoires vivantes qui construisent deux vues
synchronisées d'une même expérience :

1. une **structure relationnelle formelle**, qui conserve les participants,
   rôles, contextes, événements, états, temps, supports et contradictions;
2. une **forme distribuée contextuelle**, obtenue par liaison et superposition
   des structures actives et des souvenirs réactivés.

La vue relationnelle rend les interprétations vérifiables et composables. La vue
distribuée rend possibles l'activation graduelle, la ressemblance, le rappel
associatif, la superposition et la différenciation progressive. Aucune ne peut
être supprimée au profit de l'autre.

Elles forment une paire réversible. Le chemin relationnel → distribué construit
une forme active. Le chemin distribué → relationnel reconstruit des facteurs
candidats afin d'expliquer une activation, rejouer une interprétation, comparer
une prédiction à une nouvelle expérience et réparer les bindings responsables
d'une erreur. La reconstruction peut être ambiguë; elle retourne alors une
famille d'hypothèses plutôt qu'une fausse explication unique.

```text
expérience observée
      │
      ├── analyses formelles attribuées
      │          │
      │          ▼
      │   facteurs relationnels candidats
      │          │
      │          ├───────────────┐
      │          ▼               ▼
      │   mémoire relationnelle  forme distribuée contextuelle
      │          │               │
      │          └───────┬───────┘
      │                  ▼
      │        situation active et hypothèses
      │                  │
      ▼                  ▼
mémoire épisodique   apprentissage et consolidation
```

Les représentations externes comme MRS, TTR, WordNet, SUMO, RST ou les frames
lexicales ne constituent pas l'univers interne. Elles sont des analyses ou des
ressources attribuées qui proposent de la matière à ce cœur.

### 2.1 Système logique normatif

Seman2 est un runtime cognitif principal en mémoire, entouré de workers
d'analyse isolés et d'une persistance de checkpoint. Ce n'est pas une collection
de POC ni une chaîne de fichiers. Les composants logiques et leurs dépendances
sont les suivants :

```text
Source / curriculum / tour utilisateur
                  │
                  ▼
      [GATEWAY D'EXPÉRIENCE]
                  │ ExperienceOccurrence L0
                  ▼
        [REGISTRE D'OBSERVATION] ───────────────► [JOURNAL D'AUDIT]
                  │                                      ▲
                  ▼                                      │ copie unidirectionnelle
       [ORCHESTRATEUR D'ANALYSE]                          │
          │ jobs            ▲ résultats                  │
          ▼                 │                            │
   [WORKERS LOW LEVEL ISOLÉS]                             │
          │ AnalysisContribution L1                      │
          ▼                                              │
       [LEDGER DE CONTRIBUTIONS] ─────────────────────────┘
          │
          ▼
      [COMPOSITEUR FORMEL] ◄──────── contexte actif + structures apprises
          │ objets relationnels candidats L2
          ▼
   [GESTIONNAIRE D'HYPOTHÈSES] ◄──── contraintes / contradictions
          │ branches de situation L3
          ├──────────────► [UNIVERS RELATIONNEL VIVANT]
          └──────────────► [FORMES DISTRIBUÉES]
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
       [SYSTÈME DE MÉMOIRE L4] ◄────────► [RETRIEVAL HYBRIDE]
                 │                                 │ projection bornée
                 ├────────► [INDUCTION L5]         ▼
                 │                 │            [SOAR]
                 │                 └──► structures  │ buts/opérateurs
                 │                      réinjectées │
                 ▼                                 ▼
       [SITUATION / DISCOURS / DIALOGUE] ─► [PLAN COMMUNICATIF L6]
                                                     │
                                                     ▼
                                           [RÉALISATEUR L7]
                                                     │
                                                     └──► nouveau tour L0
```

Les flèches représentent des contrats de données autorisés. Une dépendance non
dessinée est interdite par défaut. En particulier, le compositeur, Soar,
l'induction, le dialogue et le répondant ne disposent d'aucune interface vers
les sources brutes ou le journal d'audit.

### 2.2 Composants, responsabilités et propriété d'état

| Composant | Responsabilité exclusive | État possédé | Entrées | Sorties |
|---|---|---|---|---|
| gateway d'expérience | ordonner et attribuer ce qui est vécu | curseur du curriculum et session d'entrée | source ou tour | `ExperienceOccurrence` |
| registre d'observation | conserver exactement la surface, les spans et la provenance | observations L0 immuables | expérience | références d'observation |
| orchestrateur d'analyse | router sous budget sans interpréter | jobs, barrières et raisons de non-applicabilité | observation L0 | ordres de travail |
| workers low level | produire une analyse native attribuée | aucun état cognitif durable | ordre + observation | `AnalysisContribution` L1 |
| ledger de contributions | conserver alternatives, échecs et provenance | contributions L1 append-only | résultats workers | vues typées par observation |
| compositeur formel | transformer des contributions compatibles en candidats internes | règles grammaticales génériques | L1 + situation + L5 | objets L2 |
| gestionnaire d'hypothèses | factoriser, contraindre, classer et maintenir l'indécision | beams, justifications, contradictions | L2 | branches L3 |
| univers relationnel | représenter contextes, identités, relations, événements et états admis | graphe vivant et historique | deltas L3 admis | vues/requêtes relationnelles |
| moteur de formes distribuées | lier et superposer les mêmes facteurs | vecteurs et table de décomposition | facteurs L2/L3/L4/L5 | activations et facteurs reconstruits |
| système de mémoire | gérer foyer périphérique, situation, épisodes, sémantique et oubli | contenus cognitivement accessibles L4 | monde, formes, outcomes | traces accessibles ou oubliées |
| retrieval hybride | proposer puis vérifier sous un but | index dérivés, reconstructibles | requête Soar + L4 | petit beam expliqué |
| induction | apprendre patterns, concepts et transformations | `LearnedStructure` L5 | épisodes/outcomes L4 | structures réinjectables |
| Soar | choisir l'action mentale ou communicative suivante | foyer de travail, buts, impasses, procédures | projection bornée | opérateur ou demande de retrieval |
| situation/discours/dialogue | suivre contexte multi-énoncés et interpersonnel | QUD, grounding, engagements, obligations | L2-L4 + décisions Soar | état interactionnel |
| planificateur communicatif | choisir quoi dire et sous quel statut | plan L6 inspectable | but + situation + mémoire | plan de contenu |
| réalisateur | produire une surface depuis le plan | aucun savoir caché | plan L6 | tour L7 |
| journal/checkpoint | audit scientifique et reprise atomique | événements techniques et snapshots | copies des transitions | replay et restauration |
| tuteur/évaluateur | ordonner le curriculum et mesurer des probes | rubriques et scores externes | réponses L7 | feedback devenu expérience L0 |

Un composant ne peut écrire que dans l'état dont il est propriétaire. Toute
mutation inter-composants passe par un contrat et devient un événement causal.
Le journal peut observer les transitions mais aucun composant cognitif ne peut
le consulter pour retrouver un contenu oublié.

### 2.3 Contrats de stock entre niveaux

Le stock n'est pas un nom abstrait pour une valeur reconstruite dans un test.
Il est l'objet effectivement émis par le producteur, portant au minimum :

```text
artifact_id
artifact_type
producer_id
producer_revision
experience_id
observation_refs
parent_artifact_refs
context_refs
payload_native_or_typed
epistemic_status
created_wave
content_digest
resource_cost
```

Chaque consommateur enregistre les `parent_artifact_refs` exacts qu'il a lus.
Une lignée valide doit permettre de remonter d'une réponse, d'une décision ou
d'un concept jusqu'aux observations et sorties low level qui l'ont causé. Un
champ de provenance copié sans lecture effective ne suffit pas : le consommateur
doit publier les facteurs utilisés, ignorés et la raison de chaque rejet.

Les niveaux de stock sont normatifs :

```text
L0 expérience et observation
L1 contributions d'analyse natives
L2 objets cognitifs candidats composés
L3 branches et deltas de situation
L4 contenus des mémoires vivantes
L5 structures apprises réinjectables
L6 plans mentaux et communicatifs
L7 actions ou tours réalisés
```

Un système haut niveau peut consommer plusieurs niveaux antérieurs lorsque son
contrat l'exige, mais jamais les remplacer par une fixture équivalente dans une
preuve d'intégration.

### 2.4 Dépendances et cycles autorisés

Le traitement d'une vague est acyclique de L0 vers L7. Deux boucles seulement
réintroduisent de la matière :

1. une `LearnedStructure` L5 devient une contribution interne explicitement
   attribuée lors d'une expérience ultérieure; elle repasse par composition et
   hypothèses, sans écrire directement dans l'univers;
2. un tour réalisé L7 devient une nouvelle expérience L0 du dialogue; il n'est
   pas automatiquement admis comme fait parce que le système l'a prononcé.

Le feedback d'un tuteur suit lui aussi le gateway L0. Aucune correction, sortie
d'OpenRouter, entrée de dictionnaire ou relation de banque lexicale ne possède
de raccourci vers L3, L4 ou L5.

### 2.5 Transaction d'une vague cognitive

Une vague suit cette séquence observable :

1. le gateway ouvre une expérience et fige L0;
2. l'orchestrateur calcule les branches applicables et leurs budgets;
3. les workers produisent L1 ou un échec natif explicite;
4. une barrière ferme le ledger de cette vague sans choisir un vainqueur;
5. le compositeur produit les objets L2 à partir des contributions réellement
   présentes;
6. le gestionnaire d'hypothèses construit les branches L3 et vérifie les
   contraintes;
7. Soar peut demander un retrieval borné puis choisir un opérateur;
8. le propriétaire concerné applique un delta admis à l'univers, au dialogue ou
   à la mémoire;
9. les formes distribuées et relationnelles sont synchronisées;
10. les erreurs de prédiction et outcomes deviennent matière L4;
11. l'induction peut proposer L5 pour une vague future;
12. le journal écrit la lignée et le checkpoint coordonné avance.

Un timeout de worker produit une contribution d'échec; il n'autorise pas une
analyse synthétique de remplacement. Une panne avant l'étape 12 ne déplace pas
le curseur durable. La reprise rejoue la vague depuis le dernier checkpoint et
doit produire les mêmes identifiants déterministes.

### 2.6 Déploiement initial

Le mot « service » désigne d'abord une frontière de responsabilité, pas un
microservice réseau. Le déploiement initial comprend :

- un processus runtime principal qui possède l'état cognitif en RAM;
- un processus Soar connecté par SML et limité à sa projection de travail;
- un pool borné de workers isolés pour les analyseurs lourds ou incompatibles;
- un service d'ingestion qui transforme les sources en expériences ordonnées;
- un writer de checkpoint atomique et un journal scientifique append-only;
- un processus d'évaluation externe sans droit d'écriture cognitive.

Cette forme évite de sérialiser tout l'univers entre chaque opération tout en
isolant les bibliothèques coûteuses. Une séparation en services distribués ne
sera justifiée que par des mesures de charge, jamais par la taxonomie des
modules.

### 2.7 Critère de réalité d'une intégration

Un test unitaire peut créer directement une `RelationOccurrence` pour vérifier
son invariant. Une POC n'en a pas le droit pour démontrer la compréhension d'une
phrase. Elle doit obtenir cette relation depuis une vraie observation et les
sorties réelles du niveau inférieur. De même :

- une POC de mémoire consomme des situations composées, pas des souvenirs
  instanciés à la main;
- une POC Soar consomme un vrai beam et de vrais résultats de retrieval;
- une POC de dialogue met à jour des contenus réellement compris;
- une POC culturelle consomme des épisodes, concepts et interactions réellement
  construits par le système;
- une POC chatbot entraîne deux états par ingestion avant de comparer leurs
  réponses.

Le manifeste de POC doit prouver ces arêtes. Sans cette lignée, le résultat peut
être un excellent test unitaire, mais il n'est pas une preuve du système.

---

## 3. Ce qui est inné et ce qui est appris

L'architecture doit coder les mécanismes indispensables au calcul. Elle ne doit
pas coder les connaissances particulières que le modèle est censé acquérir.

### 3.1 Primitives computationnelles admises

Le noyau peut définir :

- l'observation et sa provenance;
- l'identité d'un objet informatique et les candidats d'identité cognitive;
- la liaison entre un rôle et une valeur;
- la superposition et la réactivation;
- la distinction entre contexte, proposition, événement, état et occurrence;
- la polarité, la modalité et l'attribution à un locuteur ou une source;
- l'ordre partiel et les contraintes;
- le support, la contradiction et l'indécision;
- les opérations génériques d'ajout, retrait, remplacement, séparation,
  réunion, activation et oubli;
- les budgets de mémoire et de calcul.

Ce sont des primitives de représentation et de contrôle, pas une encyclopédie.

### 3.1.1 Compétence grammaticale formelle initiale

Seman2 ne cherche pas à reproduire le développement cognitif humain depuis une
base volontairement incompétente. Le modèle commence comme un « super-bébé »
doté d'une forte compétence grammaticale formelle.

Cette compétence comprend les mécanismes low level et high level nécessaires
pour proposer des structures :

- segmentation, morphologie, syntaxe et composition;
- portée, quantification, négation et modalité;
- prédication, rôles, événements, états et propriétés;
- référence et types possibles de référents;
- temps, aspect, ordre et persistance;
- structures de discours;
- structures de dialogue, QUD, grounding, engagements et réparations;
- espaces relationnels possibles comme possession, partie/tout, comparaison,
  localisation et transfert.

Ces éléments définissent des **représentations potentielles innées** : ils
permettent de construire et de distinguer des formes, sans fournir les faits,
concepts, effets de verbes ou conventions que le modèle doit apprendre.

Les grammaires, lexiques d'analyse et formalismes fournis avec les outils font
partie de cette compétence linguistique. Le fait qu'un analyseur connaisse une
entrée lexicale lui permet de proposer une structure; cette entrée ne devient
pas pour autant une connaissance autobiographique ou une croyance du modèle.

L'objectif n'est donc pas d'apprendre la grammaire à partir de zéro. Il est
d'utiliser une grammaire formelle riche pour apprendre le contenu, les concepts,
les transformations, les régularités et les connaissances d'un individu.

### 3.2 Contenu qui doit être acquis

Le noyau ne doit pas contenir directement :

- `apple is-a fruit`;
- une liste fermée de types d'objets du monde;
- les effets de chaque verbe;
- une liste universelle de scripts sociaux;
- une taxonomie de l'humour ou de la culture;
- une règle par mot temporel;
- un comportement conversationnel codé pour chaque formulation.

Les ressources externes peuvent proposer ces relations comme candidates, mais
le modèle doit les aligner avec ses occurrences, ses contextes et ses autres
expériences avant de les intégrer à sa propre mémoire.

La frontière entre représentation potentielle innée et contenu acquis doit
rester expérimentale et auditable. Une catégorie formelle peut être conservée
comme axe d'analyse sans devenir un concept vécu. Inversement, le système peut
apprendre des distinctions plus fines que celles prévues par les formalismes.

### 3.3 Frontière essentielle

Une fonction générique comme « lier un agent à un événement » appartient au
noyau. Une fonction comme « si le verbe est *croquer*, rendre la pomme
croquée » est une connaissance de domaine codée en dur et n'y appartient pas.

Les effets d'une famille d'événements doivent être appris à partir des cadres
lexicaux candidats, des observations avant/après, des descriptions, des
réactions, des corrections et des régularités induites.

### 3.4 Construction conceptuelle à intégration maximale

Un concept interne ne peut pas être construit uniquement à partir d'un lemme,
d'un prédicat MRS, d'un synset ou d'une cooccurrence. Sa forme doit pouvoir
intégrer toute contribution pertinente disponible :

- morphologie et construction grammaticale;
- dépendances, constituants, portée et quantification;
- rôles sémantiques et cadres événementiels;
- référence, coréférence, déixis et identité;
- propriétés, relations, possession et partie/tout;
- états, événements, causalité et transformations;
- temps, aspect, ordre et persistance;
- structure du discours et relations entre segments;
- état du dialogue, QUD, grounding et obligations;
- locuteur, engagement, modalité, registre et contexte social;
- formes orthographiques, phonologiques, symboliques ou gestuelles lorsque
  celles-ci sont pertinentes;
- épisodes antérieurs, corrections, attentes et outcomes.

Cette liste est extensible. Ajouter un analyseur ne doit pas exiger de redéfinir
le concept : il doit publier des facteurs attribués que le noyau peut soutenir,
contredire, lier, laisser en attente ou ignorer avec une raison explicite.

« Intégrer toutes les analyses » ne signifie pas les fusionner ni leur donner le
même poids. Une analyse peut :

- créer un facteur candidat;
- contraindre un binding;
- soutenir ou contredire une relation;
- distinguer deux contextes;
- provoquer la séparation d'une forme;
- réactiver un épisode;
- signaler qu'elle n'est pas applicable.

Une construction conceptuelle est incomplète lorsqu'une contribution pertinente
et disponible n'a aucun chemin vers ces opérations.

### 3.5 Politique des banques lexicales et verbales initiales

Le modèle de base ne charge pas WordNet, VerbNet, PropBank, FrameNet, SemLink ou
SUMO comme mémoire sémantique initiale. Ces banques contiennent des analyses et
distinctions humaines utiles, mais les importer comme connaissances créerait un
second système conceptuel qui court-circuiterait la biographie cognitive.

Trois espaces doivent rester distincts :

1. **compétence grammaticale initiale** : grammaires, lexiques fonctionnels,
   morphologie et entrées nécessaires aux analyseurs pour proposer une analyse;
2. **ressources analytiques externes** : banques qui peuvent proposer des sens,
   rôles ou alignements après qu'une occurrence a été observée;
3. **mémoire acquise du modèle** : formes et concepts construits uniquement par
   le cœur à partir de ses expériences et de leurs analyses attribuées.

Le lexique embarqué dans ERG ou Dynamic Syntax appartient au premier espace. Il
rend l'analyse linguistique possible, mais ne crée pas directement une croyance
ou un concept autobiographique.

Les banques du deuxième espace suivent des règles strictes :

- elles ne sont consultées qu'à propos d'une forme réellement observée;
- une absence dans la banque ne bloque aucune branche de traitement;
- leurs sorties sont des `AnalysisContribution` attribuées;
- elles ne présélectionnent pas la seule interprétation autorisée;
- leurs concepts ne deviennent pas des identités internes par copie;
- elles entrent dans le même beam que les hypothèses acquises;
- leur apport doit être mesuré par admission et ablation;
- elles ne sont jamais consultées au moment de répondre comme base de
  connaissances parallèle.

Un modèle enrichi peut recevoir ultérieurement le contenu d'une banque sous
forme d'expériences de curriculum. Il doit alors lire définitions, exemples et
relations par la chaîne normale. Cela produit un modèle ayant vécu une
éducation lexicographique plus riche, pas un runtime doté d'un oracle caché.

---

## 4. Un modèle est une biographie cognitive bornée

Un modèle est caractérisé par :

- les expériences qu'il a rencontrées;
- l'ordre de ces expériences;
- les répétitions et combinaisons observées;
- les corrections et validations reçues;
- les structures qu'il a consolidées;
- les distinctions qu'il n'a pas encore apprises;
- ses épisodes encore disponibles;
- ses limites de mémoire de travail et de mémoire à long terme;
- son état d'avancement dans un curriculum.

Un million d'expériences ne signifie pas un million de connaissances
indépendantes. Des occurrences redondantes renforcent des structures communes;
des occurrences divergentes provoquent des spécialisations; des épisodes peu
utiles s'affaiblissent; des régularités sont comprimées en structures
réutilisables.

Le contenu sémantique consolidé d'une personne peut rester relativement compact
malgré un grand nombre d'expériences. Sa puissance vient en grande partie de la
composition de formes et de relations acquises, pas de la mémorisation d'une
réponse à chaque phrase possible.

Chaque modèle possède un `ModelProfile` qui borne notamment :

```text
working_memory_capacity
active_entity_capacity
hypothesis_beam_capacity
episodic_retention_budget
semantic_consolidation_budget
retrieval_budget
induction_budget
maximum_processing_depth
curriculum_position
```

Ces capacités peuvent différer entre modèles spécialisés. Elles ne changent pas
le sens d'une observation; elles changent ce que le modèle peut maintenir,
retrouver et consolider.

---

## 5. Unités fondamentales de représentation

Les structures suivantes forment le métamodèle interne. Leurs noms décrivent
des responsabilités; leur sérialisation physique reste un choix
d'implémentation.

### 5.1 `ExperienceOccurrence`

Une expérience est un événement reçu par le modèle : phrase, tour de dialogue,
définition, code, correction, réaction ou observation structurée.

```text
experience_id
source_ref
observed_form
participants
source_order
channel
context_ref
native_structure
```

L'expérience est immuable. Les Parquet, le roman, le dictionnaire et un tour
utilisateur utilisent cette même frontière. Les métadonnées propres aux corpus
d'évaluation ne franchissent pas cette frontière.

### 5.2 `AnalysisContribution`

Chaque analyseur publie une contribution attribuée :

```text
contribution_id
experience_ref
producer
formalism
source_anchors
native_payload
projected_factors
applicability
losses
```

Les sorties ne sont pas fusionnées destructivement. Une divergence ERG / Link
Grammar / Dynamic Syntax demeure représentable.

### 5.3 `IdentityAnchor` et `SituatedFacet`

Un `IdentityAnchor` permet de reparler du même candidat d'identité. Il ne
contient pas une essence complète de l'objet.

Une `SituatedFacet` décrit la forme que prend cet objet dans un contexte donné :

```text
facet_id
identity_ref
context_ref
active_relations
active_properties
active_roles
temporal_scope
distributed_form_ref
support_refs
```

Maya dans un récit courant, Maya dans un souvenir et Maya telle qu'elle est
décrite par Paul peuvent partager un candidat d'identité tout en possédant des
facettes distinctes. Le système ne doit pas mélanger automatiquement ces
contextes.

### 5.4 `RelationOccurrence`

Une relation est n-aire et contextualisée. Elle n'est pas limitée à un triplet
sujet-prédicat-objet.

```text
relation_occurrence_id
relation_form_ref
bindings[]:
    role_form_ref
    value_ref
context_ref
temporal_scope
polarity
modality
attribution
support_refs
contradiction_refs
epistemic_state
```

Le rôle et la relation peuvent eux-mêmes pointer vers des formes apprises. Les
étiquettes provenant de VerbNet, PropBank ou FrameNet restent attribuées à ces
ressources tant qu'elles ne sont pas alignées avec une structure interne.

### 5.5 `PropositionCandidate`

Une proposition relie une ou plusieurs occurrences relationnelles sous une
portée :

```text
proposition_id
context_ref
factor_refs
scope_structure
quantification_candidates
polarity
modality
speaker_commitment
support_refs
contradiction_refs
status
```

Il n'existe pas de booléen universel `truth`. Le statut peut indiquer une
observation, une attribution, une hypothèse active, une structure consolidée,
une structure contestée ou une structure suspendue. La décision dépend du
contexte et de la provenance.

### 5.6 `EventOccurrence`, `StateFacet` et `TransitionCandidate`

Un événement relie des participants, un contexte et des contraintes
temporelles. Un état porte une relation ou une propriété pendant une étendue
temporelle. Une transformation relie des conditions et des effets candidats :

```text
TransitionCandidate
    trigger_event_ref
    binding_refs
    precondition_pattern_refs
    removed_or_closed_state_refs
    added_or_opened_state_refs
    invariant_state_refs
    temporal_constraint_refs
    support_occurrence_refs
    exception_occurrence_refs
```

Les transformations concrètes ne sont pas écrites verbe par verbe. Elles sont
induites à partir de deltas d'état récurrents et peuvent rester partielles ou
ambiguës.

### 5.7 Possession, garde, accès et partie/tout

La possession ne doit pas être réduite à une arête universelle `owns(A, B)` ni
être abandonnée au seul parseur grammatical.

La grammaire fournit plusieurs constructions candidates : possessif, génitif,
`of`, `have`, déterminants possessifs, pronoms, appositions et ellipses. Les
cadres verbaux et le discours ajoutent des transformations comme prendre,
donner, prêter, emprunter, voler, rendre, recevoir ou perdre. Le contexte doit
ensuite permettre de distinguer, sans les confondre automatiquement :

- propriété durable;
- possession temporaire;
- garde physique;
- contrôle ou accès;
- localisation auprès d'une personne;
- relation partie/tout;
- relation familiale ou associative;
- attribution conventionnelle ou juridique;
- possession métaphorique;
- simple construction grammaticale sans relation de possession pertinente.

Ces distinctions peuvent commencer comme des candidats peu différenciés. Elles
se spécialisent avec les événements, conséquences et corrections observés.

Une représentation de possession utilise donc le même contrat générique de
relation contextualisée, avec rôles, temps, modalité, provenance et état
épistémique. Une transformation de transfert propose des fermetures et ouvertures
de relations; elle ne modifie rien tant que ses bindings et conditions ne sont
pas suffisamment soutenus.

### 5.8 `ContextFrame`

Tout contenu appartient à un contexte explicite :

- situation perçue ou racontée;
- épisode;
- conversation et terrain commun;
- croyance ou parole attribuée à une personne;
- hypothèse ou condition;
- fiction;
- contrefactuel;
- plan ou intention;
- contexte d'évaluation externe, qui demeure hors cognition.

Une proposition dans la croyance de John n'est pas automatiquement une
proposition du contexte courant. Une proposition dans une histoire n'est pas
automatiquement un fait du monde du modèle.

### 5.9 `LearnedStructure`

Une structure apprise est initialement anonyme :

```text
learned_structure_id
structural_pattern
distributed_prototype
support_occurrences
exceptions
contexts_of_use
observed_outcomes
specializations
generalizations
activation_history
```

Un mot ou un nom humain peut ensuite s'aligner sur elle. Le libellé ne doit pas
être confondu avec la structure elle-même.

---

## 6. Formes distribuées et superposition structurée

### 6.1 Rôle

La forme distribuée représente ce qui est actuellement activé à propos d'un
objet, d'un événement, d'une relation ou d'un contexte. Elle n'est ni une
définition définitive, ni une table de vérité.

Une interface de Vector Symbolic Architecture ou de calcul hyperdimensionnel
est appropriée à étudier parce qu'elle fournit des opérations explicites :

- `bind(role, value)` pour lier un rôle à une valeur;
- `superpose(a, b, ...)` pour composer plusieurs contributions;
- `permute(position, value)` pour conserver un ordre;
- `similarity(a, b)` pour le rappel approximatif;
- `unbind(role, structure)` pour récupérer un candidat lié;
- `cleanup(value, candidates)` pour rapprocher un résultat d'ancres connues.

La bibliothèque NumPy déjà disponible suffit à construire et mesurer un
premier moteur. Aucune nouvelle base vectorielle n'est requise avant qu'une POC
ne démontre un besoin mesuré.

### 6.2 Construction formelle

Les vecteurs ne sont pas appris directement à partir du texte brut par une boîte
noire. Ils sont composés à partir de facteurs produits ou proposés par les
analyses formelles.

Schématiquement :

```text
Form(event_42) =
    Anchor(event_42)
    ⊕ bind(event-kind, Form(croquer))
    ⊕ bind(agent, Form(Maya@context_7))
    ⊕ bind(patient, Form(pomme@context_7))
    ⊕ bind(time, Form(interval_candidate_9))
    ⊕ bind(modality, Form(asserted_candidate))
```

Chaque terme possède une référence vers les facteurs relationnels qui l'ont
produit. Une similarité vectorielle peut proposer un rappel ou un alignement;
elle ne peut pas, seule, engager une identité ou une vérité.

### 6.3 Forme contextuelle d'une identité

```text
Form(Maya, contexte_courant) =
    identité_active
    ⊕ rôles_dans_la_situation
    ⊕ propriétés_applicables_au_contexte
    ⊕ épisodes_réactivés
    ⊕ attentes_apprises
    ⊕ alternatives_encore_actives
```

Le souvenir de Maya croquant une pomme verte hier peut donc influencer la forme
active de Maya lorsqu'elle croque une nouvelle pomme. Il devient une attente ou
un souvenir pertinent; il ne transforme pas la nouvelle pomme en pomme verte et
ne recopie pas l'ancien épisode dans le présent.

### 6.4 Synchronisation avec la structure relationnelle

Toute forme distribuée doit exposer :

- les facteurs qui la composent;
- leurs poids ou activations;
- leur contexte;
- les opérations de liaison utilisées;
- les souvenirs ayant contribué;
- les facteurs perdus lors d'une compression.

Une forme distribuée sans chemin vers ces éléments est impropre au raisonnement
cognitif principal. Elle peut servir de baseline, pas de connaissance.

### 6.5 Jouer le modèle à l'envers

Le noyau expose quatre opérations complémentaires :

```text
ENCODE   facteurs relationnels + contexte → forme distribuée
DECODE   forme distribuée + contexte → facteurs candidats
REPLAY   facteurs / concept / épisode → conséquences ou forme attendues
REPAIR   différence observé-attendu → hypothèses de correction
```

`DECODE` n'est pas une désérialisation exacte garantie. Une superposition peut
avoir perdu de l'information ou soutenir plusieurs décompositions. Le moteur
utilise les ancres, contraintes, contextes et structures relationnelles pour
produire un beam explicable de reconstructions.

`REPLAY` permet notamment de :

- reconstruire les relations attendues d'un concept;
- simuler l'application d'une transformation candidate;
- vérifier qu'une abstraction explique encore ses occurrences;
- produire une prédiction sans modifier le monde actif;
- fournir de la matière au planificateur communicatif.

`REPAIR` compare la structure prédite à l'expérience réellement analysée. Le
résidu peut conduire à :

- corriger une référence;
- rouvrir une portée ou un binding;
- diminuer l'activation d'une hypothèse;
- restaurer une alternative;
- ajouter une exception;
- spécialiser ou séparer un concept;
- réviser une transformation;
- demander une clarification.

La réparation ajoute une nouvelle trajectoire de justification. Elle ne réécrit
pas silencieusement l'expérience ou la forme antérieure.

### 6.6 Questions laissées à une POC dédiée

Le choix entre vecteurs bipolaires denses, vecteurs clairsemés, convolutions,
XOR, permutations ou tenseurs ne doit pas être décidé par intuition. La POC doit
mesurer au minimum :

- fidélité de liaison et de déliaison;
- capacité de superposition avant interférence;
- déterminisme après checkpoint;
- conservation des rôles et de l'ordre;
- séparation de contextes proches;
- rappel de combinaisons inédites;
- coût mémoire sur un grand nombre de formes;
- explication exacte par retour aux facteurs relationnels.

---

## 7. Construction structuraliste et développementale des concepts

Le système ne part pas d'une ontologie complète. Il construit d'abord des
formes grossières à partir de ressemblances et de positions relationnelles,
puis les différencie lorsque les expériences l'exigent.

```text
occurrences peu différenciées
        ↓
coactivations et rôles récurrents
        ↓
proto-structure anonyme
        ↓
prédictions et usages
        ↓
succès, exceptions et corrections
        ↓
stabilisation, spécialisation, séparation ou réunion
```

Une pomme, une poire et une balle peuvent d'abord partager plusieurs aspects de
forme et de manipulation. Les expériences alimentaires, botaniques et ludiques
introduisent progressivement des contrastes. Le concept correspondant à
« fruit » peut émerger d'un réseau de régularités, être accéléré par une
définition linguistique, puis être révisé par de nouveaux cas.

Cette approche est structuraliste parce qu'une forme dépend de ses relations et
de ses contrastes avec les autres formes. Elle est également ancrée parce que
les structures restent reliées à des expériences, événements, réactions et
conséquences observables.

### 7.1 Opérations de développement

- **renforcement** : plusieurs occurrences compatibles augmentent la stabilité;
- **différenciation** : une structure trop large se divise lorsque ses usages ou
  outcomes forment des groupes distincts;
- **spécialisation contextuelle** : une même structure conserve des facettes
  différentes selon le contexte;
- **réunion** : deux structures jusque-là séparées partagent suffisamment de
  relations et de transformations;
- **abstraction** : une structure décrit des invariants de plusieurs autres;
- **composition** : des structures acquises produisent une forme nouvelle sans
  mémorisation préalable de la combinaison complète;
- **affaiblissement** : une structure inutilisée devient moins accessible;
- **révision** : une correction ajoute une nouvelle histoire épistémique sans
  effacer l'ancienne expérience.

### 7.2 Détection des séparations

Une séparation ne doit pas être déclenchée par un mot-clé. Elle peut être
proposée lorsque plusieurs signaux convergent :

- incompatibilités de contraintes;
- distributions de rôles différentes;
- transformations ou outcomes divergents;
- contextes temporels, sociaux ou discursifs distincts;
- erreurs de prédiction répétées;
- impossibilité de compresser les occurrences sous une même structure sans
  multiplier les exceptions.

FCA, découverte de sous-graphes, ILP, statistiques et mesures de compression
peuvent chacun proposer des séparations. Aucun outil ne possède seul le pouvoir
de déclarer le concept final.

### 7.3 Fermeture récursive de la construction conceptuelle

Une structure apprise ne termine pas le traitement. Elle devient une matière
cognitive de premier ordre et peut repasser dans les systèmes de composition,
de référence, de mémoire, de contrainte, d'induction et de dialogue.

Cette fermeture récursive permet la progression suivante :

```text
formes observées
    → configurations récurrentes
    → proto-concept
    → concept stabilisé
    → concept utilisé comme participant d'une nouvelle relation
    → combinaison de concepts
    → concept de niveau supérieur
```

« Repasser dans la machine » ne signifie pas sérialiser le concept en phrase et
le faire parser artificiellement par ERG. Le runtime possède deux entrées vers
le même espace de composition :

```text
entrée exogène
    texte / dialogue / observation
        → analyseurs linguistiques
        → facteurs candidats

entrée endogène
    concept / proposition / événement / épisode activé
        → projection de ses facteurs internes
        → mêmes systèmes de contexte, liaison, hypothèses et composition
```

Les facteurs provenant des deux entrées peuvent se lier dans une même situation
active tout en conservant leur origine.

### 7.4 Référence à des objets abstraits

Une expression référentielle ne vise pas nécessairement une entité physique.
Elle peut viser :

- un individu ou un groupe;
- un événement;
- un état;
- une proposition;
- une relation;
- une transformation;
- une séquence discursive;
- un épisode;
- une structure apprise ou un concept abstrait;
- une forme linguistique elle-même dans un contexte métalinguistique.

Dans :

```text
Maya a donné sa pomme à Paul. Ça a créé une obligation.
```

`ça` peut référer à l'événement de transfert, à la proposition précédente ou à
une structure plus large de la situation. Le résolveur doit conserver ces
candidats et utiliser la grammaire, la compatibilité des rôles, le discours, le
contexte temporel, les QUD et les formes activées pour les classer.

Dans :

```text
Partager une ressource peut créer une attente de réciprocité. Ce phénomène
apparaît souvent dans ce groupe.
```

`ce phénomène` peut réactiver une structure abstraite déjà induite. Cette
structure devient alors l'argument d'une nouvelle relation portant sur un
groupe et une fréquence contextuelle. C'est ainsi que des concepts sociaux ou
culturels de niveau supérieur peuvent se former à partir de concepts plus
simples.

### 7.5 Occurrence, concept et mention de forme

Le système doit distinguer au minimum :

```text
pomme_17                         objet particulier
concept_candidate(pomme)         structure générale apprise
proposition(pomme is-a fruit)    contenu propositionnel
surface("pomme")                 forme linguistique observée
```

La phrase « *pomme* contient cinq lettres » porte sur la forme linguistique. La
phrase « cette pomme est verte » porte sur un particulier. La phrase « la pomme
est un fruit » peut porter sur une classe ou une généralisation. Une expression
comme « ça » peut viser la proposition complète. Ces objets peuvent être liés,
mais ne doivent jamais être confondus.

### 7.6 Contrôle de la récursion

La fermeture récursive ne doit pas engendrer une abstraction infinie. Une
structure repasse dans la machine seulement lorsqu'elle est :

- activée par le contexte ou une référence;
- récupérée pour expliquer ou prédire une expérience;
- candidate à une combinaison soutenue;
- requise par un but, une question ou une impasse;
- proposée à l'induction après un gain mesuré.

Le Control State borne la profondeur, le nombre de structures actives et le
budget de composition. Les dépendances récursives sont explicites; les cycles
sans nouvelle matière, réduction d'erreur ou compression sont arrêtés.

### 7.7 Vocabulaire ouvert et formes inconnues

Le système suppose qu'il rencontrera continuellement :

- des mots absents de ses mémoires;
- des néologismes;
- du slang;
- des emprunts et alternances de langue;
- des noms propres;
- des variantes dialectales;
- des fautes de frappe ou d'accord;
- des segmentations ambiguës;
- des formes volontairement non standard;
- des usages artistiques, ironiques ou communautaires.

Une forme inconnue n'est donc jamais un échec terminal ni automatiquement une
faute à corriger.

### 7.8 Observation intacte et famille d'interprétations de forme

La surface exacte est conservée avant toute normalisation. Le système construit
ensuite une `FormInterpretationFamily` pouvant contenir simultanément :

```text
observed-form-is-valid
new-lexical-form
new-inflection-or-derivation
spelling-or-typing-variation
agreement-error-with-candidate-repair
tokenization-or-segmentation-error
proper-name
borrowed-or-code-switched-form
dialect-or-community-form
deliberately-marked-or-artistic-form
quotation-or-metalinguistic-use
```

Chaque candidat conserve :

- la forme observée;
- les transformations proposées;
- les coûts orthographiques et phonologiques;
- les analyses grammaticales qu'il rend possibles;
- la compatibilité sémantique et discursive;
- les épisodes analogues;
- les supports et contradictions;
- le contexte social et le registre;
- les corrections explicites ultérieures;
- son statut de sélection révisable.

La « correction » est une hypothèse d'interprétation. Elle ne réécrit jamais
l'observation.

Lorsque aucun lexique ne reconnaît la forme, un `OpenLexicalPlaceholder`
maintient néanmoins :

```text
surface_ref
span
phonological_candidates
morphological_candidates
grammatical_category_candidates
syntactic_slot_constraints
semantic_role_slots_without_content
context_ref
```

Ce placeholder permet de construire une analyse partielle autour du mot inconnu.
Il n'invente pas sa signification. Les expériences ultérieures enrichissent ou
séparent sa forme; une correction confirmée peut l'aligner sur une forme connue.

### 7.9 Signaux de correction ou d'apprentissage

Pynini/OpenFst propose des transformations de forme pondérées. Epitran et
PanPhon apportent des proximités phonologiques; la morphologie et les analyseurs
grammaticaux mesurent la compatibilité; le discours, le dialogue et les épisodes
apportent le contexte. Les signaux comprennent :

- distance graphique et phonologique;
- transformations déjà apprises pour le locuteur ou le registre;
- accord en nombre, genre, personne ou temps;
- structure grammaticale obtenue avec chaque réparation;
- compatibilité avec les concepts et rôles actifs;
- répétition de la forme avec un usage stable;
- présence chez plusieurs locuteurs ou dans une communauté;
- guillemets, emphase, citation et contexte métalinguistique;
- réaction de l'interlocuteur;
- auto-correction ou correction tutorée;
- pouvoir prédictif de la nouvelle forme sur des occurrences ultérieures.

Une occurrence isolée proche d'une forme connue et réparant plusieurs
contraintes soutient une faute possible. Une forme répétée, stable et porteuse
d'un usage distinct soutient un apprentissage lexical. Une forme non standard
répétée dans un contexte artistique ou communautaire peut devenir une
construction marquée sans être normalisée.

### 7.10 Exemple anglais ambigu

```text
The duck are sick.
```

Au moins deux réparations minimales sont plausibles :

```text
The ducks are sick.   # correction candidate du nom
The duck is sick.     # correction candidate du verbe
```

La phrase seule peut être insuffisante pour choisir. Le nombre d'animaux dans
le contexte, les phrases voisines, les habitudes du locuteur et une correction
ultérieure peuvent modifier le ranking. Si une réponse immédiate exige une
interprétation, le système peut en sélectionner une opérationnellement tout en
conservant l'autre et en indiquant son incertitude.

### 7.11 Exemple volontairement non standard

```text
Omar m'a tuer.
```

Une analyse grammaticale standard peut proposer `tué`. Mais l'observation peut
aussi être une citation, une allusion culturelle, un titre, une imitation ou un
choix stylistique volontaire. Le système doit conserver au moins :

- la surface exacte;
- la réparation morphosyntaxique candidate;
- le contenu propositionnel candidat;
- un emplacement où une hypothèse citée ou culturellement marquée pourra être
  ajoutée si un système de haut niveau en produit réellement le support;
- les éventuels effets pragmatiques produits par le contexte de haut niveau;
- la provenance permettant de réviser le choix.

Le niveau morphosyntaxique ne doit jamais fabriquer lui-même la lecture
culturelle à partir de cette chaîne connue du développeur. Avant que le modèle
ait construit les épisodes, conventions et références nécessaires, les seules
sorties justifiées sont la surface intacte, les analyses grammaticales et
l'indécision. Comprendre le contenu et reconnaître ultérieurement la forme
artistique sont deux résultats compatibles, mais appartiennent à des niveaux de
preuve différents. Corriger intérieurement la morphologie ne donne pas au
chatbot la permission de corriger socialement son interlocuteur.

### 7.12 Apprentissage d'une nouvelle forme

Lorsqu'une forme est suffisamment soutenue, le système peut stabiliser :

- sa signature orthographique et phonologique;
- ses distributions morphologiques;
- les positions grammaticales observées;
- ses relations avec des formes voisines;
- les concepts et contextes qu'elle active;
- ses usages sociaux ou stylistiques;
- ses transformations et variantes;
- ses exceptions.

Cette forme rejoint exactement la même mémoire que les formes déjà acquises.
Elle ne demeure pas dans un « dictionnaire des inconnus » parallèle.

---

## 8. Univers relationnel vivant

### 8.1 Pas de monde unique et plat

L'univers interne est un ensemble de contextes reliés. Il contient :

- des situations actuellement actives;
- des épisodes passés;
- des connaissances sémantiques consolidées;
- des récits et mondes fictionnels;
- des croyances attribuées;
- des hypothèses conditionnelles;
- des alternatives incompatibles;
- des terrains communs propres à chaque interaction.

Le système ne doit jamais aplatir ces espaces dans un seul graphe de faits.

### 8.2 Fiabilité

Une relation est fiable parce que son histoire est inspectable, pas parce
qu'elle possède un score magique. Son état dépend notamment de :

- la reconstruction de ses occurrences sources;
- la qualité et la convergence des analyses;
- le nombre et la diversité des supports;
- les contre-exemples;
- la portée du contexte;
- les attributions de locuteur;
- les contraintes satisfaites ou violées;
- sa capacité à prédire des observations réservées;
- les corrections de tuteurs;
- sa stabilité dans le temps cognitif.

Une agrégation numérique peut aider au ranking. Elle ne remplace jamais ces
dimensions.

### 8.3 Admission dans la mémoire sémantique

L'admission suit un processus explicite :

```text
proposition candidate
    → validation des bindings
    → vérification des contextes et portées
    → résolution locale des contraintes
    → recherche de supports et contradictions
    → comparaison avec les structures existantes
    → décision opérationnelle de traitement
    → consolidation, suspension ou maintien comme hypothèse
```

Soar peut contrôler quelle opération exécuter, quoi maintenir en mémoire de
travail et quelle recherche lancer. Il ne décrète pas arbitrairement qu'une
proposition est vraie.

### 8.4 Interrogation

Une requête est traduite dans les mêmes facteurs que l'ingestion. Le moteur :

1. active les formes et identités pertinentes;
2. récupère les épisodes et structures candidates;
3. suit les relations et transformations applicables;
4. respecte les contextes, la polarité et la temporalité;
5. matérialise seulement les combinaisons nécessaires;
6. retourne une réponse, plusieurs possibilités ou une ignorance;
7. conserve un chemin explicatif vers les expériences utilisées.

Répondre à « une pomme est-elle un fruit? » doit donc suivre une relation
acquise ou une chaîne d'inférences acquises. La présence des deux mots dans un
corpus ou dans WordNet n'est pas une réponse cognitive suffisante.

---

## 9. Événements, états et transformations apprises

### 9.1 Modèle général

```text
StateContext S0
    ↓ EventOccurrence E1
StateContext S1
    ↓ EventOccurrence E2
StateContext S2
```

Un événement n'écrase pas l'état antérieur. Il ouvre un nouvel état relié au
précédent et conserve les invariants, changements, incertitudes et alternatives.

### 9.2 Apprentissage d'une transformation

Pour une famille d'événements, le système rassemble :

- les bindings récurrents des participants;
- les états observés avant;
- les états observés après;
- les propriétés invariantes;
- les conséquences décrites ou constatées;
- les exceptions;
- les utilisations métaphoriques, hypothétiques ou fictionnelles;
- les cadres proposés par les ressources lexicales.

IND-03 peut proposer des structures récurrentes; IND-04 des deltas récurrents;
Popper des règles candidates; Z3 en vérifie la compatibilité locale; Soar
contrôle leur application active. L'application n'est consolidée que dans le
contexte où ses conditions sont soutenues.

### 9.3 Persistance et temps

Le temps cognitif primaire est relationnel : ordre entre observations,
événements, états, épisodes et contextes. Les coordonnées calendaires restent
des ancres externes.

Les systèmes disponibles sont utilisés ainsi :

- ordre source pour les relations observables;
- Reichenbach pour les candidats E/R/S;
- algèbre d'Allen pour les contraintes d'intervalles;
- DRT/SDRT et aspect pour les candidats discursifs;
- Z3 pour la propagation et les incompatibilités locales.

HeidelTime et Duckling ne font pas partie du chemin temporel principal. Leurs
règles, lexiques et normalisations codent des catégories et conversions qui
risquent d'imposer une temporalité étrangère au modèle relationnel. Ils restent
temporairement disponibles comme baselines diagnostiques hors cognition. Une
POC d'admission peut tester une contribution de surface strictement attribuée;
sans gain net démontré, ils doivent être retirés plutôt que maintenus par
habitude.

Une expression comme « encore » ou « plus tard » ne doit pas être remplacée
irréversiblement par une valeur normalisée ou une fonction écrite pour ce mot.

---

## 10. Mémoires

### 10.1 Mémoire de travail

Soar maintient une projection bornée de la situation courante : buts,
hypothèses actives, entités, contraintes, opérateurs et résultats de retrieval.
Le store global n'est jamais copié dans la working memory.

### 10.1.1 Espace cognitif actif

Le projet n'affirme pas résoudre philosophiquement ou neuroscientifiquement la
conscience. Opérationnellement, le « présent cognitif » du modèle est un espace
couplé :

```text
Active Cognitive Workspace
    = Soar Working Memory
    + Active Situation Graph
    + Active Distributed Form Field
    + bounded hypothesis beam
    + temporarily retrieved memories
    + Control State
```

Soar en est le noyau exécutif : buts, attention, opérateurs, impasses,
préférences, demandes de retrieval et procédures apprises. Il n'est pas le
contenant de toute la cognition. Les formes distribuées, l'univers relationnel,
les mémoires acquises, les contraintes formelles et les analyseurs restent dans
leurs systèmes propriétaires.

Une représentation devient disponible au contrôle conscient opérationnel
lorsqu'une projection bornée entre dans cet espace actif. De nombreuses formes
peuvent recevoir une faible activation sans être injectées dans Soar.

### 10.1.2 Soar n'est pas suffisant seul

Soar ne fournit pas à lui seul :

- la composition sémantique linguistique;
- les formes distribuées et leur déliaison;
- l'univers relationnel contextualisé;
- la découverte de concepts;
- le moteur général de transformations d'état;
- la résolution temporelle et dialogique complète;
- le retrieval structurel global;
- la politique de consolidation et d'oubli recherchée ici.

Ses mémoires sémantique et épisodique peuvent porter certaines structures et
procédures utiles. Elles ne remplacent pas les mémoires spécialisées du runtime.

### 10.1.3 Foyer, périphérie et mémoire accessible

La frontière utile n'est pas « dans Soar = conscient, hors Soar = inconscient ».
Le système distingue trois degrés d'accès immédiat :

1. **foyer explicite** : objets projetés dans la working memory Soar, disponibles
   pour les règles, opérateurs et décisions;
2. **périphérie active** : formes et relations suffisamment activées pour
   influencer le ranking, l'attention et le retrieval, sans occuper une WME;
3. **mémoire latente** : structures non actives, accessibles seulement par une
   opération de rappel.

La périphérie explique qu'une association puisse orienter l'interprétation sans
devenir une pensée explicitement manipulée. Si elle franchit un seuil ou résout
une impasse, une projection structurée entre dans Soar. Si elle perd son
activation, elle redevient latente sans avoir été sélectionnée.

### 10.1.4 Couches temporelles de mémoire

Les couches sont définies par persistance et accessibilité, pas par une durée
murale universelle :

| Couche | Contenu | Persistance | Accès et propriétaire principal |
|---|---|---|---|
| tampon d'observation | surface courante, ancres, états incrémentaux, sorties en attente | mots ou vague courante | scheduler, analyseurs et Artifact Arena |
| champ actif périphérique | formes partiellement activées, sens candidats, relations locales | vague courante ou quelques transitions | moteur distribué et graphe de situation |
| foyer de travail | buts, contraintes critiques, petit beam, opérateurs, résultats de retrieval | tant que le but ou sous-but le maintient | Soar Working Memory |
| contexte de situation | participants, QUD, terrain commun, sujet, ordre, état courant | plusieurs tours ou un épisode | Active Situation Graph et mémoire dialogue/discours |
| mémoire intermédiaire | épisodes récents, formes encore labiles, hypothèses en attente, traces de répétition | plusieurs épisodes et réactivations | mémoire épisodique et consolidation |
| mémoire longue | concepts stabilisés, relations soutenues, transformations, épisodes distinctifs, procédures | jusqu'à affaiblissement, révision ou oubli | mémoires relationnelle, distribuée, épisodique et procédurale |
| journal expérimental | sources et traces nécessaires à l'audit scientifique | politique de l'expérimentateur | extérieur à la cognition et inaccessible au chatbot |

Un même contenu peut être représenté à plusieurs couches sans être dupliqué en
entier. Soar reçoit des identifiants, bindings et résumés actifs vers des
structures qui restent la propriété de leurs mémoires.

### 10.1.5 Transitions entre couches

```text
observation
    → analyse et activation périphérique
    → projection éventuelle dans le foyer Soar
    → intégration au contexte de situation
    → trace intermédiaire
    → consolidation ou oubli

mémoire longue
    → indice de retrieval
    → réactivation périphérique
    → projection éventuelle dans Soar
```

Les facteurs de promotion comprennent pertinence au but, nouveauté, répétition,
distinctivité, erreur de prédiction, correction et utilité passée. La simple
présence d'une phrase ne garantit pas sa consolidation.

Les facteurs de retrait comprennent fin du but, changement de sujet, faible
utilité, concurrence, décroissance, interférence et compression. Retirer un
objet du foyer n'est pas l'oublier; oublier exige la disparition ou la perte de
reconstructibilité depuis les mémoires propres du modèle.

### 10.1.6 Usage précis des mémoires natives Soar

- **Working Memory** porte le foyer explicite.
- **Episodic Memory** peut mémoriser des configurations de contrôle et des
  projections de situation vécues par Soar; elle ne remplace pas l'épisode
  relationnel complet.
- **Semantic Memory** peut conserver des LTI et associations utiles au contrôle,
  avec des références vers les structures conceptuelles propriétaires.
- **Production Memory et chunking** conservent des procédures et raccourcis de
  décision appris.

Cette répartition doit être mesurée. Une structure ne doit pas être dupliquée
dans Soar uniquement parce qu'une mémoire native existe.

### 10.2 Mémoire épisodique

Elle conserve des expériences situées, leurs participants, leur ordre, leurs
contextes et les formes actives au moment de l'expérience. Tous les épisodes ne
restent pas également accessibles.

### 10.3 Mémoire sémantique

Elle conserve les structures consolidées, leurs variantes, supports,
exceptions, domaines d'application et liens vers les épisodes. Elle n'est pas
une ontologie universelle préchargée.

### 10.4 Mémoire procédurale

Elle conserve des procédures de contrôle, de dialogue, de raisonnement et des
transformations apprises. Le chunking Soar peut généraliser une opération, mais
le chunk obtenu doit rester attribué aux situations qui l'ont justifié.

### 10.5 Mémoire des formes

Elle conserve les ancrages distribués, les superpositions consolidées, les
alignements entre modalités et les index nécessaires au rappel approximatif.

### 10.6 Mémoire culturelle

Elle conserve tardivement des structures récurrentes portant sur des épisodes
complets : relations sociales, attentes, actions, réactions, transmissions,
outcomes et exceptions. Elle ne doit pas apprendre la culture à partir de
simples comptes de mots ou de prédicats isolés.

### 10.7 Journal expérimental externe

Les corpus bruts, Parquet, Arrow et fichiers sources restent extérieurs au
modèle. Ils servent à l'ingestion, à la reproductibilité scientifique et à
l'audit de l'expérience. Ils ne constituent pas une mémoire autobiographique
parfaite accessible au chatbot.

Le journal expérimental peut conserver l'ordre d'ingestion, une ancre de temps
source et les observations présentées. Il appartient à l'expérimentateur, pas au
sujet cognitif. DuckDB peut l'inspecter pendant une évaluation technique, mais
aucune commande cognitive ou conversationnelle ne peut l'interroger pour
retrouver une connaissance oubliée.

Rejouer une ancienne source est une nouvelle exposition explicite dans un run
d'apprentissage. Ce n'est pas un rappel interne.

### 10.8 Oubli et compression

Sous pression mémoire, le système peut :

- réduire l'activation;
- laisser disparaître des détails non consolidés;
- conserver temporairement certains épisodes dans une mémoire intermédiaire;
- conserver des épisodes représentatifs et des exceptions;
- remplacer de nombreuses occurrences actives par une structure apprise tout
  en acceptant que certains détails deviennent cognitivement irrécupérables;
- abandonner des hypothèses faibles du contexte actif sans les réécrire en
  fausses;
- renforcer par répétition ce qui doit persister;
- oublier réellement certains contenus selon une politique mesurable.

La persistance exige normalement réactivation, répétition, utilité,
distinctivité ou consolidation explicite. Elle n'est pas garantie par le seul
fait qu'une phrase a été ingérée.

Le journal externe peut prouver qu'une expérience a autrefois été présentée,
mais le modèle doit être évalué à partir de ce qu'il peut encore reconstruire
depuis ses propres mémoires. Cette séparation empêche de déguiser un système RAG
en mémoire humaine.

Un checkpoint restaure l'état cognitif utile : mémoires vivantes, structures
consolidées, contexte actif, état Soar, curriculum et curseurs. Il ne ressuscite
pas un contenu déjà oublié. Il n'est pas nécessaire d'embarquer toutes les
données sources dans le modèle.

---

## 11. Topologie d'exécution

Un service est ici une responsabilité logique. Le déploiement initial reste un
runtime principal en mémoire accompagné de workers isolés :

```text
┌──────────────────────────────────────────────────────────────────┐
│ RUNTIME COGNITIF                                                 │
│                                                                  │
│ scheduler par vagues                                             │
│ mémoires relationnelles et distribuées                           │
│ gestionnaire d'hypothèses                                        │
│ modèle de situation                                              │
│ retrieval et induction                                           │
│ Soar et Control State                                            │
└──────────────┬──────────────────────────────────┬────────────────┘
               │ jobs bornés                       │ checkpoint
               ▼                                   ▼
┌─────────────────────────────┐       ┌────────────────────────────┐
│ WORKERS D'ANALYSE ISOLÉS    │       │ PERSISTANCE               │
│ ERG, DS, Link Grammar, RST, │       │ journal causal, index,    │
│ code, phonologie, NLG       │       │ mémoire durable, snapshot │
└─────────────────────────────┘       └────────────────────────────┘
```

Cette topologie exige une arène d'artefacts, un scheduler borné, des workers, un
Control State et un checkpoint coordonné. Les anciennes implémentations peuvent
être consultées dans l'archive, mais aucune n'est réputée active avant la POC
verticale qui démontre son contrat dans ce graphe.

### 11.1 Propagation par vagues

Une vague traite les conséquences immédiates d'une expérience. Un feedback ou
une nouvelle abstraction ouvre une vague ultérieure. Cela évite les boucles
instantanées et rend le replay déterministe.

Les modules déclarent :

- leurs types d'entrée et de sortie;
- leurs préconditions;
- leur coût;
- leurs domaines de mémoire;
- les raisons explicites de non-applicabilité;
- les facteurs consommés et produits.

Le succès ne se mesure plus au fait qu'un module a été appelé. Il faut prouver
que sa matière pertinente a contribué à une forme, une hypothèse, une décision,
une consolidation ou une réponse.

### 11.2 Routage pertinent

« Utiliser tous les systèmes » signifie utiliser tous les systèmes pertinents
pour l'expérience. Tree-sitter ne doit pas analyser une phrase ordinaire et la
phonologie n'a pas à décider seule d'une appartenance conceptuelle. Une branche
non applicable publie une raison; une branche applicable mais inutilisée est un
défaut d'intégration.

### 11.3 Ressources physiques

Les limites de RAM, workers, temps et taille de lot sont extérieures aux choix
cognitifs. Soar peut répartir son attention à l'intérieur de ces limites, jamais
les dépasser. Les analyseurs lourds, notamment RST, restent isolés et ne sont
pas lancés lorsque leur sortie n'est pas requise.

### 11.4 Retrieval hybride piloté par un but

Soar ne demande pas « tout ce qui ressemble à maison ». Il émet une requête
structurée depuis le but courant, la situation et l'impasse :

```text
RetrievalRequest
    goal_ref
    anchor_form_refs
    required_role_bindings
    context_refs
    temporal_constraints
    discourse_and_dialogue_constraints
    requested_memory_kinds
    maximum_graph_hops
    maximum_abstraction_steps
    maximum_episode_expansions
    beam_width
    activation_floor
    novelty_reserve
    time_and_work_budget
```

Le moteur combine deux directions :

1. la similarité distribuée propose rapidement des formes et épisodes proches;
2. le matching relationnel vérifie participants, rôles, contexte, temps,
   contraintes et provenance.

Selon le but, une requête structurelle peut aussi précéder la recherche
distribuée. Aucun score de similarité ne suffit à engager une interprétation.

Les résultats retournés à Soar sont peu nombreux et diversifiés. Le reste
demeure latent dans les mémoires propriétaires.

### 11.5 Profondeur de pensée et approfondissement progressif

La profondeur n'est pas un unique nombre de sauts. Elle possède plusieurs axes :

- distance dans le graphe relationnel;
- distance dans l'espace distribué;
- nombre de niveaux d'abstraction;
- nombre d'épisodes ouverts;
- profondeur de dérivation;
- nombre de branches concurrentes;
- distance temporelle ou contextuelle;
- coût total de calcul.

Le runtime approfondit progressivement :

```text
niveau 0 : forme, construction et bindings locaux
niveau 1 : phrase, événement et contraintes immédiates
niveau 2 : tours voisins, QUD, discours et situation courante
niveau 3 : épisodes proches, habitudes du locuteur et concepts directement liés
niveau 4 : patterns abstraits et analogies structurelles
niveau 5 : associations lointaines, seulement sur impasse ou but créatif
```

Il s'arrête lorsque :

- le but est satisfait;
- une interprétation possède un support suffisant pour l'action demandée;
- les expansions supplémentaires n'apportent plus d'information utile;
- le budget est épuisé;
- les candidats restants sont incompatibles avec le contexte;
- le système choisit de demander une clarification.

Une interprétation peut rester épistémiquement incertaine même si Soar choisit
une action opérationnelle.

### 11.6 Attention, inhibition et styles cognitifs

La pertinence dépend conjointement de :

- compatibilité des rôles et contraintes;
- contexte discursif et QUD;
- proximité temporelle et épisodique;
- identité du locuteur et registre;
- activation antérieure;
- succès de prédiction passé;
- similarité distribuée;
- nouveauté;
- but actuel.

Les branches incompatibles sont inhibées sans être détruites. Les associations
répétitivement inutiles perdent de l'activation dans ce contexte.

Des paramètres comme une faible inhibition, une grande réserve de nouveauté, une
décroissance lente ou un beam large peuvent produire un style plus associatif
et distractible. Cela peut rappeler certains aspects d'un profil ADHD, sans
constituer un modèle clinique ni un diagnostic. Un style créatif peut ouvrir
plus volontiers les associations lointaines; une tâche factuelle privilégie les
bindings directs.

### 11.7 Induction et ambiguïté n'utilisent pas la même profondeur

Pour corriger une ambiguïté online, le système commence localement et n'élargit
la recherche qu'en cas d'impasse. Pour l'induction, il peut comparer un ensemble
plus large d'épisodes hors du contexte actif, mais toujours sous budget :

```text
index distribué ou structurel
    → petit ensemble de candidats
    → comparaison exacte des sous-graphes et deltas
    → proposition de pattern
    → test sur occurrences réservées
    → éventuelle consolidation
```

Soar peut planifier ou interrompre cette opération. Il ne charge jamais tous les
épisodes dans sa working memory et l'induction ne se limite pas aux quelques
objets actuellement présents dans Soar.

### 11.8 Exemple de contrôle associatif : « maison »

Dans :

```text
Maya a acheté une maison.
```

`acheter`, le rôle de thème, le contexte matériel et les épisodes voisins
activent d'abord la forme correspondant à un bâtiment ou un lieu de résidence.
Les relations directement utiles — possession, localisation, occupants,
transaction — peuvent entrer dans la situation active.

Des formes comme « maison de Dieu », une commande apprise adressée à un chien,
une maison astrologique ou une maison commerciale peuvent recevoir une faible
activation lexicale. Elles ne franchissent pas le seuil de la working memory en
l'absence de contexte religieux, canin, astrologique ou commercial.

Si le texte est :

```text
Bienvenue dans la maison de Dieu le Père.
```

les relations `de`, le registre et le contexte discursif changent le retrieval
et la lecture institutionnelle ou religieuse devient pertinente.

Si un épisode contient une personne disant « maison! » à son chien, le locuteur,
le destinataire, l'intonation disponible et l'historique interactionnel peuvent
réactiver une construction de commande propre à cet usage.

Le système ne parcourt donc pas consciemment toutes les significations à chaque
mot. Le champ distribué offre une activation graduelle; les contraintes
relationnelles et le contrôle déterminent ce qui devient matière de réflexion.

---

## 12. Flux d'ingestion

```text
1. lire une expérience dans l'ordre du curriculum
2. créer l'observation immuable et son contexte
3. enregistrer les formes connues et inconnues sans correction destructive
4. construire les interprétations concurrentes de forme
5. lancer les analyseurs applicables sur les candidats autorisés en parallèle
6. conserver chaque sortie native, échec et analyse partielle
7. projeter des facteurs formels sans fusion prématurée
8. proposer identités, relations, événements, états et portées
9. construire les formes distribuées candidates
10. réactiver les épisodes et structures pertinentes
11. former un beam diversifié d'interprétations compatibles
12. vérifier contraintes, contextes et contradictions
13. construire les mises à jour et transformations candidates
14. laisser Soar contrôler les opérations et la mémoire active
15. admettre, suspendre ou rejeter les mises à jour avec justification
16. mettre à jour les mémoires relationnelles et distribuées
17. mesurer erreurs de prédiction, nouveautés et récurrences
18. déclencher l'induction lorsque le Control State l'autorise
19. consolider, différencier, comprimer, affaiblir ou oublier
20. enregistrer une trace explicative et avancer le curriculum
```

Les couches hautes ne relisent jamais les Parquet. Elles consomment les formes,
épisodes, relations et structures réellement produits en dessous.

Le dictionnaire JSONL suit exactement ce flux. Sa structure native indique qu'un
document présente un mot, une catégorie déclarée, une glose et des exemples.
Elle ne crée pas automatiquement la relation interne exprimée par la glose.

---

## 13. Flux chatbot

Le mode chatbot ne possède pas une chaîne de compréhension séparée :

```text
tour utilisateur
    → même observation et mêmes analyses
    → mise à jour candidate du contexte dialogique
    → activation de la situation et des mémoires
    → interprétations concurrentes
    → raisonnement ou recherche interne
    → but communicatif
    → plan inspectable
    → réalisation linguistique
    → nouveau tour observé par le système
```

Le plan communicatif est construit avant la surface. SimpleNLG peut réaliser
les cas anglais couverts; les limites de langue restent explicites. Le texte
généré devient ensuite une occurrence du dialogue, sans être automatiquement
considéré comme une nouvelle vérité.

Le modèle doit pouvoir produire :

- une réponse soutenue avec son chemin de justification;
- plusieurs réponses possibles lorsque l'ambiguïté demeure;
- une demande de clarification;
- une correction de sa réponse précédente;
- un refus motivé;
- une déclaration d'ignorance.

---

## 14. Discours et dialogue comme structures cognitives

Le dialogue n'est pas un emballage autour du graphe sémantique. Il modifie la
portée et le statut des connaissances.

Le Dialogue Gameboard et les mises à jour ISU doivent suivre :

- le terrain commun public;
- les propositions seulement évoquées;
- les engagements de chaque participant;
- les QUD actives;
- le grounding gradué;
- les obligations discursives;
- les réparations;
- les sujets et références actifs;
- les attentes concernant le prochain tour.

Dynamic Syntax apporte des états incrémentaux; ERG une structure profonde;
DiAML des annotations de fonctions communicatives; SDRT/RST des propositions de
structure discursive. Ces sorties sont des contributions, pas le dialogue
interne lui-même.

Une affirmation ironique, une citation ou un énoncé dans une fiction peut
partager un contenu littéral avec une assertion factuelle tout en créant un
engagement différent. La mémoire doit conserver cette séparation.

---

## 15. Curriculum et développement par échelons

### 15.1 Rôle du curriculum

Le curriculum construit les fondations dans un ordre où les nouvelles
expériences peuvent être interprétées à partir des formes déjà acquises.

`data/the_map_of_everything_nlp_novel.txt` est un premier matériau léger visant
à imiter une expérience linguistique graduelle. Il est imparfait et ne doit pas
être traité comme une vérité de référence ou comme le curriculum complet.

Un `CurriculumStage` contient :

```text
stage_id
prerequisite_capabilities
ordered_experience_sets
reinforcement_sets
heldout_probes
fixed_evaluation_criteria
promotion_policy
remediation_policy
```

### 15.2 Progression indicative

Les échelons précis doivent être expérimentés, mais la dépendance générale est :

1. formes observées, segmentation, identité d'occurrence;
2. objets particuliers, propriétés et relations simples;
3. actions, participants, états et changements;
4. identité entre phrases, ordre et épisodes;
5. quantification, négation, modalité et contextes enchâssés;
6. questions, réponses, grounding et réparation;
7. récits, explications, causalité et transformations apprises;
8. abstraction, concepts hiérarchiques et combinaisons inédites;
9. attentes sociales, pragmatiques et culturelles;
10. dialogue ouvert sur la connaissance effectivement acquise.

Cette liste n'est pas une ontologie imposée. Elle organise des capacités de
traitement et des dépendances développementales.

### 15.3 Redondance et combinaison

Chaque étape fournit :

- plusieurs occurrences de structures proches;
- des variations de surface;
- des combinaisons nouvelles de formes déjà apprises;
- des contre-exemples;
- des corrections explicites;
- des cas volontairement indécidables;
- des probes qui n'ont pas été présentés pendant l'apprentissage.

Le passage d'un échelon exige de généraliser à ces probes, pas de retrouver une
phrase mémorisée.

---

## 16. Tuteurs et évaluation externe

### 16.1 Critères définis avant l'évaluation

Le LLM externe n'invente ni le curriculum ni les critères après avoir vu le
résultat. Chaque probe possède à l'avance :

- la capacité évaluée;
- les entrées autorisées;
- les invariants déterministes;
- les dimensions nécessitant un jugement sémantique;
- les seuils de passage;
- les comportements acceptables en cas d'incertitude;
- les informations qui doivent rester cachées au modèle cognitif.

### 16.2 Ordre des évaluations

1. vérifications déterministes de structure, provenance et contraintes;
2. vérifications comportementales exactes lorsqu'un oracle existe;
3. évaluation LLM des dimensions ouvertes selon la grille fixée;
4. comparaison à des baselines;
5. décision de progression ou de renforcement.

OpenRouter et `OPENROUTER_TEXT_MODEL` servent uniquement à l'étape 3. La clé, le
modèle externe, ses réponses et les labels d'évaluation ne sont jamais présents
dans les mémoires cognitives ni dans la décision de production.

Le tuteur sait quelles expériences ont été présentées au modèle. Il construit
donc ses questions à partir des connaissances qui devraient être accessibles à
ce stade et des capacités visées par l'échelon. Il ne teste pas arbitrairement
la culture générale du LLM évaluateur.

### 16.3 Correction tutorée

Une évaluation externe ne change pas directement le modèle et ne bénéficie
d'aucune autorité cognitive cachée. Son rôle normal est de vérifier les critères
sur le contenu déjà ingéré.

Si une étape prévoit exceptionnellement une remédiation, le contrôleur de
curriculum peut présenter plus tard de nouvelles expériences ou corrections
explicitement attribuées. Elles repassent alors par toute la chaîne cognitive;
la réponse d'évaluation elle-même n'est jamais injectée.

### 16.4 Exemple de gate

Pour une étape portant sur objets, classes et propriétés :

- créer deux individus distincts à partir de deux occurrences;
- maintenir une identité entre deux mentions;
- distinguer propriété particulière et généralisation;
- répondre à une combinaison tenue à l'écart;
- citer les relations internes utilisées;
- rester indécis si le support est insuffisant;
- ne pas consulter le dictionnaire ou le LLM au moment de répondre.

---

## 17. Outils existants et rôle exact

La présence d'un outil dans le dépôt ne lui garantit aucune place dans le chemin
cognitif. Chaque outil doit démontrer une contribution nette. Il peut être :

- **admis** dans le chemin principal;
- **routé conditionnellement** pour certaines formes d'expérience;
- **quarantainé** comme annotation externe ou baseline;
- **réservé à l'évaluation**;
- **retiré** s'il nuit davantage qu'il n'aide.

L'évaluation d'un outil porte au minimum sur :

- la structure supplémentaire réellement fournie;
- sa précision et ses échecs sur les expériences visées;
- sa capacité à conserver les ambiguïtés;
- son risque d'imposer une taxonomie ou des concepts externes;
- les pertes lors de l'adaptation;
- sa compatibilité avec les autres contributions;
- son effet mesuré sur des probes tenus à l'écart;
- son coût en RAM, temps, complexité et maintenance;
- sa reproductibilité;
- sa capacité à expliquer sa contribution.

Un outil est nuisible s'il provoque notamment davantage de faux engagements, de
collapse d'hypothèses, de contamination ontologique, d'interférences ou de
pannes qu'il n'apporte de pouvoir explicatif ou prédictif. Le fait qu'il soit
reconnu, installé ou déjà couvert par une POC ne suffit pas à le conserver.

Le tableau suivant est donc un inventaire de candidats et de frontières, pas
une liste permanente de dépendances obligatoires.

| Domaine | Outils disponibles | Rôle retenu | Ce qu'ils ne décident pas |
|---|---|---|---|
| Grammaire profonde | ACE, ERG, PyDelphin | HPSG, MRS, EDS, DMRS, portée et ancres | vérité, identité finale, sens lexical choisi |
| Syntaxe complémentaire | Link Grammar | linkages attribués et couverture secondaire | fusion automatique avec ERG |
| Analyse incrémentale | `dynamicsyntax`, DyLan comme référence | états mot par mot et structures TTR candidates | état dialogique complet ou sens final |
| Banques lexicales | WordNet, VerbNet, PropBank, FrameNet, SemLink | candidats optionnels après observation, dans le beam commun | mémoire initiale, filtre obligatoire ou lookup de réponse |
| Ontologie externe | SUMO et mappings WordNet | baseline et propositions d'alignement en POC | import global de vérités ou accès runtime parallèle |
| Forme et phonologie | Epitran, PanPhon, CMUdict/Flite | IPA, traits et candidats attribués | identité sémantique |
| Transformations de forme | Pynini/OpenFst, Phonetisaurus | WFST, n-best, alignements, coûts | relation sémantique finale |
| Temps | ordre source, Reichenbach, Allen, Z3 | relations, contraintes, cohérence locale | horloge cognitive universelle |
| Temps de surface | HeidelTime, Duckling | baselines diagnostiques hors chemin principal; admission non acquise | mémoire temporelle ou normalisation imposée |
| Discours | IsaNLP RST, TextTiling, STAC/DISRPT | segmentations et relations attribuées | mémoire discursive ou culture interne |
| Dialogue | DialogBank/DiAML, DGB/ISU internes | fonctions communicatives de référence et état public | intention privée imposée par un label |
| Coréférence | CoreNLP, Coreferee, mécanismes internes | chaînes candidates et comparaison | identité engagée sans autres preuves |
| Code | Tree-sitter | CST, erreurs et structures partielles | signification fonctionnelle complète |
| Graphes | NetworkX, rustworkx | hypergraphes projetés, matching, parcours | politique cognitive |
| Contraintes | Z3, NuWLS-c | satisfiabilité, modèles, nogoods, optimisation locale | vérité globale ou meilleur sens universel |
| Induction conceptuelle | odis/FCA | treillis et regroupements formels | concept culturel final |
| Induction logique | Popper, SWI-Prolog | règles candidates avec couverture et exceptions | admission automatique comme connaissance |
| Statistiques | DuckDB, Polars, NumPy, SciPy | agrégats, signaux, tests et mesures | intention ou causalité par corrélation |
| Stockage et audit | Arrow, Parquet, DuckDB, Zstandard | sources, journal expérimental, mesures et scans bornés | mémoire oubliée, RAG conversationnel ou bus cognitif actif |
| Contrôle | Soar et SML | buts, opérateurs, impasses, mémoire de travail et procédures | ontologie ou vérité décrétée |
| Réalisation | SimpleNLG | surface anglaise depuis un plan explicite | choix du contenu à dire |
| Corpus conversationnels | ConvoKit, Switchboard, Reddit, Stack Overflow | expériences et analyses descriptives | réponses à consulter par le chatbot |
| Évaluation | OpenRouter | jugement externe selon critères fixés | cognition, retrieval ou génération runtime |

### 17.1 Décision d'admission continue

Une POC analytique répond à « que produit cet outil? ». Une POC d'admission doit
ensuite répondre à « cette production améliore-t-elle réellement la construction
et l'utilisation des formes? ».

Le test compare au minimum le cœur avec et sans la contribution sur le même
curriculum et les mêmes probes. Un outil est déclassé ou retiré lorsque son gain
n'est pas démontré dans les limites de ressources du modèle.

### 17.2 Limites connues à considérer lors de l'admission

- Le port Dynamic Syntax Python est expérimental et DyLan ne constitue pas
  encore un contrôle reproductible complet.
- PropBank et SemLink ont des écarts de couverture et de correspondance entre
  ressources locales.
- FrameNet et SUMO sont des ressources, pas des détecteurs automatiques fiables
  de la structure présente dans une phrase.
- IsaNLP RST est lourd en mémoire et doit rester hors du chemin court.
- SimpleNLG installé couvre principalement l'anglais.
- Les votes Reddit et autres réactions de plateforme sont des outcomes bruités,
  pas une mesure directe de l'humour ou de la culture.
- Les analyseurs peuvent échouer ou diverger. Le runtime doit conserver cet
  état au lieu de fabriquer une analyse de remplacement.

---

## 18. Politique d'archive et réintroduction contrôlée

### 18.1 Mécanismes recherchés

- observation et provenance immuables;
- Artifact Arena et identifiants causaux;
- scheduler borné par vagues;
- workers d'analyse isolés;
- conservation des sorties natives;
- hypothèses factorisées, justifications et contradictions;
- beam diversifié;
- Z3 et les contraintes temporelles relationnelles;
- bridge borné entre stockage global et Soar;
- checkpoint et reprise exacte;
- retrieval structurel dans les mémoires encore accessibles;
- journal expérimental externe pour l'audit, strictement séparé du modèle;
- planification communicative séparée de la réalisation.

Cette liste décrit les mécanismes que le nouveau système doit fournir. Elle ne
conserve automatiquement ni une implémentation, ni un outil, ni une POC de
l'ancien système. Le code archivé peut servir de référence, puis doit être
réintroduit derrière le contrat actif et prouvé sur le stock réel de l'étage
inférieur.

### 18.2 À remplacer ou approfondir

- `semantic-structure` ne doit plus être une simple projection locale de MRS;
- `episode-candidate` doit contenir une situation relationnelle et ses formes,
  pas seulement une référence à une famille d'hypothèses;
- les statistiques ne doivent pas se limiter aux comptes de prédicats et de
  constantes;
- l'induction doit porter sur relations, sous-graphes, séquences et deltas;
- `cultural-learning-state` ne peut pas être produit par un seuil sur des traits
  isolés;
- `memory-consolidation-state` doit appliquer une mise à jour cognitive réelle
  lorsqu'elle est suffisamment soutenue;
- les marqueurs actuels `world_update_performed = false` et
  `truth_committed = false` ne peuvent plus constituer le succès terminal du
  système d'ingestion;
- la validation « tous les modules ont participé » doit devenir « toute matière
  pertinente a influencé une structure ou possède une raison explicite de ne
  pas l'avoir fait ».

### 18.3 Statut des anciennes POC

Toutes les anciennes POC, y compris les premières POC `CORE-*`, sont hors du
périmètre actif. Leurs résultats peuvent indiquer qu'une bibliothèque sait
produire une structure locale, mais ils ne démontrent pas :

- l'acquisition graduelle d'un univers relationnel;
- la formation contextualisée d'une identité;
- l'apprentissage général des effets des verbes;
- la consolidation sémantique après de nombreuses expériences;
- la progression par curriculum;
- un chatbot répondant exclusivement depuis sa biographie cognitive.

Leurs verdicts ne sont donc pas des verdicts du nouveau système. Une capacité
est réintroduite seulement par une POC `SYS-*` de `plans/required_poc.md` qui
consomme les vrais artefacts de l'étage précédent.

### 18.4 Code candidat présent dans le dépôt

Certains modules écrits pendant l'exploration implémentent déjà des fragments
utiles :

- `developmental_core` implémente contextes, identités, facettes, relations
  n-aires, événements, états, transitions génériques et formes distribuées
  traçables;
- `cognitive_memory` et `attention_controller` implémentent les degrés d'accès,
  les capacités bornées, la consolidation par répétition, l'oubli inaccessible
  et le retrieval progressif avec raison d'arrêt;
- `concept_learning` induit des structures anonymes, teste des combinaisons
  tenues à l'écart et propose des spécialisations sur outcomes divergents;
- `open_vocabulary` conserve les surfaces exactes, les placeholders et les
  réparations concurrentes;
- `cognitive_artifacts` fournit des invariants d'identité, causalité et lignée
  pour des artefacts typés;
- `semantic_admission` déduplique les analyses par expérience, consolide sous
  seuils explicites et conserve les révisions contradictoires;
- `grammatical_composition` dérive une prédication de classe depuis la structure
  copulaire MRS sans règle portant sur un lexème particulier;
- `curriculum` sépare expériences, probes, critères préenregistrés et
  évaluations externes;
- `cognitive_query` produit ignorance, qualification épistémique et chemins de
  preuve depuis la seule mémoire accessible.

Les anciens adaptateurs formels, services d'ingestion, schedulers et commandes
intégrées ont été déplacés dans `archives/ancien_systeme/runtime/`. Ils peuvent
inspirer SYS-01, mais ne sont pas importables par le runtime actif.

Ces modules sont des candidats, pas un cœur admis. Les tests qui construisent
leurs objets à la main restent des tests unitaires. Même l'expérience
« An apple is a fruit. » ne devient une preuve système qu'après exécution de la
chaîne L0→L4 avec un manifeste de lignée et sans reconstruction manuelle entre
les étages. L'implémentation active commence donc à SYS-01 et progresse dans
l'ordre; aucun ancien `GO` n'est reporté.

---

## 19. Contrats de causalité significative

Une chaîne de parents techniques ne suffit pas. Chaque sortie de haut niveau
doit publier un `ContributionTrace` :

```text
consumer_artifact_ref
input_factor_ref
producer_artifact_ref
operation
effect_on_output
activation_or_weight_change
context_ref
reason_if_ignored
```

Exemples d'effets :

- création d'un binding;
- ajout ou retrait d'une contrainte;
- activation d'un souvenir;
- changement de classement d'une hypothèse;
- ouverture d'une alternative;
- proposition d'une transformation;
- renforcement ou séparation d'une structure apprise;
- modification d'un plan de réponse.

Une validation terminale doit pouvoir répondre :

1. Quelles observations ont produit cette connaissance ou cette réponse?
2. Quelles analyses ont contribué à chaque facteur?
3. Quelles alternatives ont été conservées ou rejetées, et pourquoi?
4. Quel contexte autorise l'affirmation?
5. Quel souvenir ou pattern a été réactivé?
6. Quelle opération Soar a choisie?
7. Quelle modification réelle des mémoires en a résulté?

---

## 20. Exemple cible complet : Maya croque une pomme

Expériences antérieures :

```text
Hier, dans l'histoire, Maya a croqué une pomme verte.
La pomme avait ensuite une morsure.
```

Nouvelle expérience :

```text
Maya croque une pomme.
```

Le traitement attendu est :

1. ERG propose une structure événementielle et des arguments;
2. Dynamic Syntax propose une construction incrémentale compatible ou
   divergente;
3. les ressources lexicales proposent des cadres et rôles candidats;
4. le résolveur de référence réactive l'identité candidate de Maya;
5. une nouvelle identité particulière de pomme est créée, sauf preuve qu'il
   s'agit d'une pomme déjà connue;
6. un événement courant reçoit les bindings agent/patient candidats;
7. le système temporel distingue l'événement courant de l'épisode d'hier;
8. la forme active de Maya superpose son identité, son rôle courant et le
   souvenir pertinent;
9. la forme de la nouvelle pomme n'hérite pas automatiquement de `verte`;
10. le souvenir soutient une attente de transformation de la pomme;
11. cette attente demeure candidate tant que l'outcome n'est pas observé ou
    suffisamment consolidé;
12. l'épisode courant est ajouté avec son contexte et ses alternatives;
13. les statistiques et l'induction reçoivent le sous-graphe et le delta, pas
    seulement les tokens `Maya`, `croque`, `pomme`;
14. une question ultérieure peut distinguer ce qui est observé, rappelé,
    attendu ou encore inconnu.

Questions possibles :

```text
Qui croque la pomme ?
Qu'est-ce que Maya a croqué hier ?
La nouvelle pomme est-elle verte ?
Que pourrait-il arriver à la pomme ?
```

Réponses attendues :

- Maya est soutenue comme agent de l'événement courant;
- la pomme verte appartient à l'épisode d'hier;
- la couleur de la nouvelle pomme est inconnue;
- une morsure peut être une conséquence attendue, mais doit être présentée
  selon le statut réellement acquis par le modèle.

Cet exemple vérifie simultanément identité, facettes contextuelles,
superposition, mémoire épisodique, temps, événement, transformation apprise,
incertitude et interrogation.

---

## 21. Programme d'implémentation

### Étape A — Noyau représentationnel isolé en tests unitaires

Construire et tester sans NLP :

- contextes;
- identités et facettes;
- relations n-aires;
- propositions et statuts épistémiques;
- événements, états et transformations;
- structure relationnelle persistante;
- formes distribuées liées aux facteurs;
- requêtes avec chemins explicatifs.

Les fixtures sont formelles et ne présument pas que le NLP sait déjà les
produire. Cette étape produit des tests unitaires, pas une POC ni un verdict
d'intégration.

### Étape B — Superposition et différenciation en tests unitaires

Mesurer :

- composition rôle/valeur;
- rappel et interférence;
- activation contextuelle;
- séparation de proto-concepts;
- réunion de formes équivalentes;
- génération de combinaisons tenues à l'écart;
- déterminisme du checkpoint.

### Étape C — Début des POC verticales depuis les analyseurs réels

Brancher les sorties existantes :

- registre ouvert des formes et familles de correction/apprentissage;
- Pynini, Epitran et PanPhon pour les transformations candidates;
- ERG/MRS en premier;
- alignements Dynamic Syntax et Link Grammar;
- candidats lexicaux externes uniquement dans le chemin attribué et optionnel;
- référence et temps;
- discours et dialogue lorsque la matière l'exige.

Les adaptateurs doivent être génériques. Aucun test ne peut être réussi par une
règle portant sur les mots exacts de la fixture.

### Étape D — Consolidation et mémoire bornée

Ajouter :

- admission épistémique;
- soutien et contradiction;
- compression épisodique;
- structures sémantiques consolidées;
- mémoires de travail, intermédiaire et consolidée;
- oubli mesurable;
- reprise exacte du modèle.

### Étape E — Curriculum exécutable

Transformer le roman, le dictionnaire et de petits dialogues tutorés en
expériences ordonnées. Définir les probes et critères avant chaque étape.

### Étape F — Dialogue et réponse

Faire répondre le chatbot depuis l'état acquis, avec ignorance explicite,
chemins de justification, réparation et plan communicatif inspectable.

### Étape G — Induction haute et culture

Réintroduire l'induction culturelle seulement lorsque les patterns portent sur
des épisodes relationnels complets et que leur effet sur des probes réservés est
mesurable.

---

## 22. Gates d'acceptation architecturaux

Le nouveau cœur n'est pas considéré fonctionnel tant que les démonstrations
suivantes ne passent pas sans règles lexicales propres aux fixtures.

### Gate 1 — Identité et contexte

- deux mentions compatibles peuvent partager une identité candidate;
- deux contextes incompatibles gardent des facettes séparées;
- une croyance rapportée n'est pas engagée dans le contexte courant.

### Gate 2 — Relations et requêtes

- une expérience crée des relations n-aires interrogeables;
- une réponse suit une chaîne interne;
- chaque étape retourne sa provenance;
- l'absence de chaîne produit une ignorance, pas une invention.

### Gate 3 — État et transformation

- plusieurs événements transforment successivement le même objet;
- l'état final respecte l'ordre relationnel;
- les états antérieurs restent inspectables;
- une transformation apprise se généralise à de nouveaux participants.

### Gate 4 — Superposition

- une forme active combine identité, contexte, rôles et souvenirs;
- une propriété de l'ancien épisode ne fuit pas dans le nouvel épisode;
- le rappel pertinent améliore une prédiction tenue à l'écart;
- chaque composante distribuée revient à un facteur explicite.

### Gate 5 — Développement conceptuel

- un proto-concept émerge d'occurrences sans label interne imposé;
- des outcomes divergents provoquent une séparation justifiée;
- une nouvelle combinaison est traitée sans mémorisation de la phrase;
- les exceptions restent accessibles.

### Gate 6 — Mémoire bornée

- une longue ingestion respecte les limites physiques;
- la mémoire active reste bornée;
- la périphérie active peut influencer un ranking sans être copiée dans Soar;
- seule une projection justifiée franchit le seuil du foyer de travail;
- quitter la working memory ne provoque pas automatiquement l'oubli;
- les structures consolidées survivent à la compression;
- un épisode encore mémorisé peut être réactivé sans relire la source;
- un contenu oublié ne réapparaît pas par consultation du journal externe;
- la répétition améliore effectivement la persistance;
- la reprise restaure le même comportement.

### Gate 7 — Curriculum et tuteur

- les critères sont enregistrés avant les résultats;
- les probes sont absents des expériences d'apprentissage;
- le LLM externe ne reçoit aucun pouvoir sur le runtime;
- une correction n'est apprise qu'après être devenue une expérience attribuée;
- un palier refusé déclenche un renforcement ciblé.

### Gate 8 — Chatbot autobiographique

- deux modèles aux expériences différentes répondent différemment lorsque leur
  connaissance diffère;
- chacun répond correctement sur son propre vécu;
- chacun reconnaît au moins certaines lacunes;
- aucun ne consulte les corpus ou OpenRouter pour produire sa réponse.

### Gate 9 — Vocabulaire ouvert et réparation

- toute surface inconnue traverse le système même sans entrée lexicale;
- l'observation exacte survit à toutes les corrections candidates;
- `The duck are sick` conserve les réparations nominale et verbale tant que le
  contexte ne les départage pas;
- une correction explicite ultérieure change le ranking sans réécrire le passé;
- une nouvelle forme récurrente rejoint la mémoire lexicale commune;
- un usage volontairement non standard peut conserver sa forme et sa fonction;
- une correction interprétative n'entraîne pas automatiquement une correction
  adressée à l'interlocuteur;
- aucun lookup dans une banque initiale n'est requis pour apprendre la forme.

### Gate 10 — Attention et profondeur de retrieval

- une interprétation locale claire n'ouvre pas inutilement les associations
  lointaines;
- une impasse déclenche un approfondissement mesurable et borné;
- la recherche distribuée retrouve des candidats que le matching exact peut
  ensuite confirmer ou rejeter;
- `maison` n'active dans Soar que les sens soutenus par la situation;
- un contexte religieux, canin ou commercial peut réordonner ces formes;
- un but créatif peut élargir la profondeur sans modifier les croyances;
- l'induction compare davantage d'épisodes que la compréhension online sans les
  charger dans la working memory;
- chaque arrêt indique le but satisfait, le gain marginal insuffisant, la
  clarification choisie ou le budget atteint.

---

## 23. Anti-patterns interdits

- considérer la présence d'un artefact terminal comme preuve de compréhension;
- compter l'exécution des modules sans mesurer leur contribution;
- coder une fonction sémantique par verbe, mot ou fixture;
- transformer WordNet, SUMO ou le dictionnaire en vérité interne immédiate;
- charger une banque lexicale comme mémoire initiale ou système de réponse;
- refuser une observation parce que le mot est absent des banques;
- corriger la surface avant d'avoir conservé l'observation exacte;
- assimiler toute forme non standard à une erreur;
- remplacer les relations par une similarité vectorielle;
- remplacer les formes distribuées par un graphe figé sans activation;
- aplatir croyances, fiction, hypothèses et monde courant;
- sélectionner systématiquement un candidat lorsqu'il faut rester indécis;
- réduire le temps à des timestamps;
- laisser HeidelTime ou Duckling définir le temps cognitif;
- apprendre la culture à partir de labels ou comptes lexicaux seulement;
- faire lire les Parquet aux systèmes haut niveau;
- faire répondre le chatbot depuis une question Stack Overflow retrouvée;
- utiliser le journal d'ingestion comme RAG ou mémoire autobiographique parfaite;
- utiliser OpenRouter dans la cognition ou comme générateur de réponses;
- appeler « consolidation » une opération qui ne modifie aucune mémoire;
- appeler « univers » une collection d'analyses de phrases indépendantes.

---

## 24. Conséquence immédiate pour le projet

La prochaine intégration ne doit pas ajouter une relation taxonomique spéciale
ni continuer directement les POC culturelles.

Elle doit d'abord construire le noyau représentationnel générique décrit ici,
puis démontrer sur des entrées formelles et linguistiques que :

```text
expériences
    → formes contextuelles
    → relations et événements
    → états et transformations
    → mémoires consolidées
    → requêtes et comportements futurs
```

Les anciennes POC sont archivées et n'ont aucun statut actif. Le nouveau
programme est défini uniquement dans `plans/required_poc.md`. Une idée ou un
adaptateur archivé peut être repris, mais il doit traverser à nouveau la preuve
verticale correspondant à sa place dans le graphe L0→L7.

Le critère directeur est désormais :

> Une expérience a-t-elle modifié de manière explicable la forme interne des
> objets, relations, événements et contextes concernés, et cette modification
> influence-t-elle correctement une expérience ou une réponse ultérieure?
