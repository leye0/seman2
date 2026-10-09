# Architecture d’un système cognitif symbolique généraliste

## Architecture cible — maxiformalisme linguistique et conversationnel, acquisition sémiotique ouverte, hypothèses factorisées, état symbolique composable et temporalité relationnelle, sans ontologie cognitive hardcodée

# 1. Objectif

Construire un système capable d’ingérer un univers textuel massif, de transformer les textes en structures analysables, d’accumuler des expériences, puis de découvrir progressivement ses propres abstractions, concepts, régularités, stratégies et structures discursives.

Le système vise à terme un comportement conversationnel généraliste comparable, dans son rôle, à un petit chatbot de type GPT, mais avec une architecture explicite, inspectable et symbolique.

Principes :

- le langage brut est fortement analysé avant le raisonnement ;

- les représentations sont explicites et inspectables ;

- les connaissances conservent leur provenance ;

- l’apprentissage principal repose sur l’induction de structures ;

- les mémoires cognitives vivent principalement en RAM pendant l'exécution et
  sont rendues persistantes par checkpoints coordonnés, journal de reprise et
  stockage froid réversible sous pression ;

- le contexte actif reste petit ;

- le système ne reçoit pas une liste prédéfinie de « choses qu’il doit savoir faire » ;

- les catégories conceptuelles et discursives utiles doivent émerger de l’expérience ;

- une forme inconnue, atypique ou nouvelle reste une observation exploitable même si aucun analyseur ne sait encore la catégoriser ;

- plusieurs analyses formelles d’une même forme peuvent coexister sur des plans différents — graphique, phonologique, morphologique, syntaxique, sémantique, discursif, pragmatique et contextuel — sans être fusionnées prématurément.

- les possibilités locales doivent être conservées aussi largement que raisonnablement possible, mais leurs combinaisons globales ne doivent être matérialisées que lorsqu’un calcul les exige ;

- une interprétation sélectionnée à un instant donné n’efface jamais les hypothèses concurrentes ni le fait historique qu’une autre interprétation avait pu être préférée auparavant ;

- l’incertitude persistante doit être représentée sous forme factorisée, avec justifications, supports, contradictions, provenance et contraintes, plutôt que comme une duplication de mondes complets.

---

# 2. Contrainte absolue : aucun catalogue cognitif hardcodé

Le système ne doit pas contenir une liste prédéfinie de catégories représentant ce que nous espérons qu’il comprendra ou fera.

Il ne faut donc pas concevoir un espace cognitif fermé de la forme :

```text

CATEGORY_A

CATEGORY_B

CATEGORY_C

...

```

où nous déciderions à l’avance que certaines catégories correspondent à des types de réponses, de raisonnements, de conversations ou de concepts du monde.

Le système doit produire lui-même des structures comme :

```text

Pattern_1827

Pattern_92104

Concept_771

Schema_88

Transformation_412

```

puis découvrir que certaines sont équivalentes, imbriquées, spécialisées, généralisables, composables ou utiles dans des contextes similaires.

Les noms humains peuvent être ajoutés ensuite uniquement comme outil d’inspection.

---

# 3. Ce qui peut être hardcodé

On peut hardcoder les mécanismes généraux nécessaires à la computation symbolique :

```text

create

link

bind

compare

retrieve

activate

deactivate

copy

compose

decompose

merge

split

generalize

specialize

count

rank

measure

store

forget

trace provenance

track time

apply constraint

test consistency

generate candidate

evaluate candidate

select candidate

```

Ces opérations ne sont pas des connaissances du monde.

On peut également hardcoder les formats nécessaires pour lire des sources externes : structure HTML, schéma d’un dump Stack Overflow, arbre Reddit, markup Wikipédia, blocs de code, citations, timestamps, reply links, identifiants, etc.

> On peut hardcoder comment lire une source.

> On ne hardcode pas ce que la source signifie.

---

# 4. Ce qui ne doit pas être hardcodé

Le système ne doit pas recevoir comme primitives cognitives une taxonomie du monde ou du discours.

Il ne doit pas dépendre d’une liste prédéfinie censée représenter :

- des types de problèmes ;

- des types de réponses ;

- des types d’explications ;

- des types de conversations ;

- des types d’humour ;

- des types de récits ;

- des types d’intentions ;

- des types de stratégies conversationnelles.

Si de telles structures sont utiles, elles doivent émerger du corpus.

Le système peut découvrir qu’un groupe de transformations présente une structure récurrente, créer une abstraction et la réutiliser.

---

# 5. Principe central : des structures construites à partir de structures

```text

observations

    ↓

motifs récurrents

    ↓

structures composées

    ↓

abstractions

    ↓

abstractions d’abstractions

    ↓

structures procédurales réutilisables

```

La qualité du système dépend principalement de son moteur d’induction, pas du nombre de règles manuelles.

---

# 6. Deux régimes de fonctionnement

## 6.1 OFFLINE INGESTION

```text

corpus massif

    ↓

Source Layer

    ↓

Observation Graph

    ↓

Transmission / Provenance Graph

    ↓

analyses externes linguistiques / phonologiques / formelles

    ↓

hypothèses cross-représentation / acquisition sémiotique ouverte

    ↓

gestion factorisée des hypothèses et des justifications

    ↓

analyses conversationnelles formelles

    ↓

épisodes

    ↓

induction

    ↓

Learned Graph

    ↓

mémoire globale

```

Détail :

```text
CORPUS
   │
   ▼
SOURCE LAYER / DECODER
   │
   ▼
OBSERVATION GRAPH
   │
   ▼
TRANSMISSION / PROVENANCE GRAPH
   │
   ├────────────────┬─────────────────┬────────────────┐
   ▼                ▼                 ▼                ▼
TEXT NLP       FORM / PHONO       CODE PARSERS   SOURCE-NATIVE
ERG / MRS      ANALYZERS                         INTERACTION LINKS
/etc.          Epitran / PanPhon
   │           OpenFst / Pynini
   │                │
   ├──────────────┐ │
   │              ▼ ▼
   │       DYNAMIC SYNTAX / DyLan
   │       incremental dialogue grammar
   │              │
   └──────────────┴──────────────┬─────────────────────┘
                                  ▼
                    ANNOTATED OBSERVATION GRAPH
                                  │
                                  ▼
                 CROSS-REPRESENTATION HYPOTHESES
           orthography / phonology / symbols / semantics
              alternatives + provenance + uncertainty
                                  │
                                  ▼
                   FORMAL DIALOGUE ANALYSES
              DIT++ / ISO 24617-2 / SDRT / KoS
                                  │
                                  ▼
                   DIALOGUE-STATE UPDATE TRACES
             ISU / grounding / obligations / QUD
                                  │
                                  ▼
                  FACTORIZED HYPOTHESIS MANAGER
          justifications / contradictions / constraints
          structural sharing / no Cartesian expansion
                                  │
                                  ▼
                              EPISODES
                                  │
                                  ▼
                         GLOBAL STATISTICS
                                  │
                                  ▼
                         PATTERN DISCOVERY
                                  │
                                  ▼
                       CANDIDATE STRUCTURES
                                  │
                                  ▼
                     EVALUATION / COMPRESSION
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                      PROMOTE           DISCARD
                         │
                         ▼
                    LEARNED GRAPH
                         │
                         ▼
                    GLOBAL MEMORY
```

Cette boucle peut fonctionner continuellement sur de très grandes quantités de données. Elle ne cherche pas à répondre immédiatement : elle transforme l’expérience en mémoire et en abstractions.

## 6.2 ONLINE INTERACTION

```text

nouveau texte utilisateur

    ↓

Source / interaction context

    ↓

Observation Graph

    ↓

Transmission / Provenance links

    ↓

analyses linguistiques, phonologiques et sémantiques structurées

    ↓

hypothèses cross-représentation / acquisition sémiotique ouverte

    ↓

analyses conversationnelles formelles

    ↓

candidats de mise à jour de l’état de dialogue

    ↓

factorisation des hypothèses + récupération de leurs justifications historiques

    ↓

révision incrémentale des supports / contradictions / contraintes

    ↓

composition paresseuse de quelques interprétations globales

    ↓

beam actif borné et structurellement diversifié

    ↓

mise à jour du contexte actif et de l’état interactionnel

    ↓

récupération mémoire

    ↓

récupération sélective de provenance pertinente

    ↓

raisonnement

    ↓

construction de transformations candidates

    ↓

sélection

    ↓

planification communicative

    ↓

réalisation linguistique

    ↓

réponse

    ↓

nouvel épisode avec provenance explicite

```

Détail :

```text

USER TEXT

   │

   ▼

SOURCE / INTERACTION CONTEXT

   │

   ▼

OBSERVATION GRAPH

   │

   ▼

TRANSMISSION / PROVENANCE LINKS

   │

   ▼

LINGUISTIC / SEMANTIC ANALYSES
ERG / MRS / temporal / lexical / reference candidates
   │
   ├──────────────────────────┐
   │                          ▼
   │                 FORM / PHONO ANALYSES
   │          Epitran / PanPhon / OpenFst / Pynini
   │          multiple candidates, never normalization
   │                          │
   ├───────────────┐          │
   │               ▼          │
   │       DYNAMIC SYNTAX / DyLan
   │       incremental interpretation
   │               │          │
   └───────────────┴──────────┴───────────┐
                                          ▼
                          CROSS-REPRESENTATION BUNDLE
                    orthographic / phonological / lexical
                    symbolic / semantic / contextual links
                                          │
                                          ▼
                         UTTERANCE INTERPRETATION BUNDLE
                                  │
                                  ▼
                    FORMAL DIALOGUE ANALYSES
                 DIT++ / ISO / SDRT / KoS-TTR
                                  │
                                  ▼
                  INFORMATION-STATE UPDATE CANDIDATES
                  grounding / obligations / QUD / repair
                                  │
                                  ▼
                    FACTORIZE LOCAL HYPOTHESES
          phonology / syntax / reference / semantics / dialogue
                                  │
                                  ▼
                   RETRIEVE PRIOR JUSTIFICATIONS
             support / contradiction / provenance / outcomes
                                  │
                                  ▼
                     REVISE EVIDENCE LEDGER
            preserve history; do not rewrite prior selections
                                  │
                                  ▼
                    LAZY INTERPRETATION COMPOSITION
              instantiate only combinations needed now
                                  │
                                  ▼
                     BOUNDED DIVERSE ACTIVE BEAM
               top candidates + structurally novel reserves
                                  │
                                  ▼
                    UPDATE ACTIVE GRAPH + INTERACTION STATE

   │

   ▼

MEMORY RETRIEVAL

   │

   ▼

RETRIEVE RELEVANT PROVENANCE

   │

   ▼

REASONING / CONSTRAINT PROPAGATION

   │

   ▼

GENERATE CANDIDATE TRANSFORMATIONS

   │

   ▼

EVALUATE CANDIDATES

   │

   ▼

SELECT TRANSFORMATION

   │

   ▼

COMMUNICATIVE PLANNING

   │

   ▼

SURFACE REALIZATION

   │

   ▼

RESPONSE

   │

   ▼

STORE NEW EPISODE WITH EXPLICIT PROVENANCE

```

L’interaction online produit donc elle-même de nouvelles expériences qui pourront être réingérées dans la boucle offline.

---

# 7. Vue générale

```text

                           CORPUS MASSIF

                               │

                               ▼

                    ┌─────────────────────┐

                    │    SOURCE LAYER     │

                    │ structure native    │

                    │ contexte d’origine  │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │  OBSERVATION GRAPH  │

                    │ matériau observable │

                    │ structure native    │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │    TRANSMISSION /   │

                    │  PROVENANCE GRAPH   │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐
                    │ EXTERNAL ANALYSES   │
                    │ grammar / semantics │
                    │ phonology / form    │
                    │ code / source       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ ANNOTATED           │
                    │ OBSERVATION GRAPH   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ CROSS-REPRESENTATION│
                    │ HYPOTHESES          │
                    │ form / sound /      │
                    │ symbol / meaning    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ FORMAL DIALOGUE     │
                    │ ANALYSES            │
                    │ DS / ISO / SDRT /   │
                    │ KoS-TTR / ISU       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ FACTORIZED          │
                    │ HYPOTHESIS MANAGER  │
                    │ evidence / nogoods  │
                    │ lazy composition    │
                    │ structural sharing  │
                    └──────────┬──────────┘

                               │

                 ┌─────────────┴─────────────┐

                 ▼                           ▼

          EPISODIC STORE              STRUCTURE STORE

                 │                           │

                 └─────────────┬─────────────┘

                               ▼

                    ┌─────────────────────┐

                    │  INDUCTION ENGINE   │

                    │ motifs              │

                    │ compression         │

                    │ abstraction         │

                    │ merge / split       │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │   GLOBAL MEMORY     │

                    │  live RAM + indexes │

                    │ checkpoint / cold   │

                    └──────────┬──────────┘

                               │

                          retrieval

                               │

                               ▼

                    ┌─────────────────────┐

                    │   ACTIVE CONTEXT    │

                    │       SOAR          │

                    │ working memory      │

                    │ goals / retrieval   │

                    │ chunking            │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │ CANDIDATE GENERATOR │

                    │ graph transforms    │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │      SELECTION      │

                    │ utility / evidence  │

                    │ constraints         │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │ COMMUNICATIVE PLAN  │

                    │ content / discourse │

                    │ reference / style   │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │     REALIZATION     │

                    │ linguistic output   │

                    └──────────┬──────────┘

                               │

                               ▼

                            RESPONSE

```

---

# 8. Source Layer

Avant toute interprétation, il faut conserver la structure d’origine.

Lorsque la source fournit explicitement une relation, on la conserve : document, auteur, thread, parent, réponse, timestamp, code block, citation, score, vote, tag, historique d’édition, etc.

Ces éléments constituent le **Source Graph**.

Ils ne sont pas des abstractions cognitives.

Exemple Stack Overflow :

```text

Thread T483

Post P1

  author = U17

  native_type = question

  timestamp = ...

  score = ...

Segment S1

  parent = P1

  modality = natural_language

Segment S2

  parent = P1

  modality = code

  declared_language = python

Post P2

  author = U88

  native_type = answer

  parent = P1

  accepted = true

  score = ...

Comment C1

  author = U39

  attached_to = P2

```

`native_type` est une propriété fournie par la source, pas une catégorie cognitive imposée au moteur.

---

# 9. Observation Graph : conservation intégrale de l’expérience observable

## 9.1 But

Avant toute interprétation linguistique, sémantique ou discursive, le système doit construire une représentation persistante de **tout ce qui a effectivement été observé dans la source**.

Cette représentation est appelée **Observation Graph**.

Son rôle n’est pas de comprendre la donnée.

Son rôle est de garantir qu’aucune information observable n’est détruite simplement parce qu’un analyseur existant ne lui attribue pas de signification.

Le principe est :

> Toute portion observable de la source demeure représentable, adressable et réutilisable par l’induction, qu’un analyseur externe sache ou non la classifier.

Ainsi, la sortie d’un tokenizer, d’un parseur grammatical ou d’un autre analyseur n’est jamais la totalité de l’entrée cognitive.

Elle constitue seulement une couche d’annotations ajoutée au-dessus de l’expérience observée.

---

## 9.2 Aucun partage fondamental entre « langage » et « bruit »

Le système ne doit pas effectuer à l’entrée une séparation conceptuelle définitive de la forme :

```text

recognized_language

vs

noise

```

Il ne doit pas non plus créer une catégorie générique telle que :

```text

OTHER

UNKNOWN

NON_WORD

PUNCTUATION

FORMATTING

```

comme destination pour tout ce qui n’a pas été analysé lexicalement.

Une portion non reconnue par un analyseur reste simplement une portion observable qui possède moins d’annotations externes à ce moment précis.

Elle peut ultérieurement :

- réapparaître ;

- entrer dans des motifs récurrents ;

- être reliée à d’autres structures ;

- être regroupée avec d’autres occurrences ;

- acquérir une fonction prédictive ;

- devenir une abstraction induite ;

- participer à une abstraction de plus haut niveau.

Autrement dit :

```text

absence d’analyse

≠

absence d’information

```

---

## 9.3 Niveau le plus bas : fidélité à la source

Le système doit pouvoir revenir à la source originale sans reconstruction approximative.

Le Source Layer fournit donc une représentation fidèle de la donnée reçue et des structures explicitement présentes dans son format.

L’Observation Graph est construit par-dessus cette représentation.

À ce niveau, la seule distinction fondamentale est entre :

```text

ce qui provient directement de la source

```

et :

```text

ce qui a été ajouté par un analyseur ou induit ultérieurement

```

La méthode de décodage du média peut être déterministe.

Par exemple, un flux textuel encodé doit nécessairement être décodé pour être manipulable.

Ce décodage est une opération d’entrée/sortie, pas une classification cognitive.

Le système peut conserver suffisamment d’information pour relier toute unité manipulée à sa position dans la source originale.

---

## 9.4 Unités observables

L’Observation Graph doit permettre de référencer des unités et des ensembles d’unités sans leur imposer une interprétation fonctionnelle.

Conceptuellement :

```text

Source S

  contains U0

  contains U1

  contains U2

  ...

```

Les unités possèdent une identité et des relations structurelles minimales provenant du support ou du format.

Des ensembles contigus ou structuraux peuvent ensuite être référencés par des spans :

```text

Span A -> U17 .. U24

Span B -> U25 .. U25

Span C -> U26 .. U31

```

Un span ne signifie pas automatiquement :

```text

word

sentence

paragraph

punctuation

heading

emphasis

```

Il désigne simplement une portion de l’expérience observable.

Un analyseur externe peut ensuite proposer l’une de ces interprétations.

L’induction interne peut également finir par découvrir ses propres regroupements.

---

## 9.5 Les analyses externes sont ajoutées, jamais substituées

Supposons qu’une source contienne une séquence quelconque.

Un analyseur lexical peut reconnaître une portion de cette séquence et produire une annotation.

Conceptuellement :

```text

ObservationSpan_182

    ↓

ExternalAnalysis_917

```

avec :

```text

producer = Analyzer_X

result = ...

```

Un autre analyseur peut produire une autre structure sur une région qui chevauche la première :

```text

ObservationSpan_180_190

    ↓

ExternalAnalysis_441

```

Les deux analyses coexistent.

L’Observation Graph reste inchangé.

Aucun analyseur n’a le droit de remplacer les observations originales par sa propre segmentation du monde.

---

## 9.6 Les mots eux-mêmes sont des analyses

Même la reconnaissance d’une unité lexicale doit conceptuellement rester une analyse attachée à une portion observable.

Le système peut recevoir :

```text

Analyzer_X:

  span S47 corresponds to lexical structure L19

```

Puis d’autres analyseurs peuvent enrichir cette structure.

Mais le span d’origine continue d’exister indépendamment.

Ainsi, si une portion n’est reconnue par aucun analyseur lexical, elle n’est pas rejetée.

Elle reste disponible pour l’induction exactement comme n’importe quelle autre portion de l’expérience.

Le même principe vaut pour la phonologie, les abréviations, les jeux graphiques, les symboles et les normalisations possibles. Une analyse peut proposer qu’un span possède une réalisation phonologique, ressemble à une autre forme, admet une segmentation alternative ou évoque une notation connue ; aucune de ces propositions ne remplace le span observé.

En particulier, une opération de « correction » orthographique ou de normalisation ne doit jamais modifier l’Observation Graph. Elle crée au mieux une **relation candidate attribuée** vers une autre structure.

---

## 9.7 Tout résidu demeure cognitivement disponible

Considérons une source contenant :

```text

ABC???

DEF

```

Le système ne doit pas décider à l’avance que certaines portions appartiennent à une catégorie cognitive particulière et que les autres ne sont que de la mise en forme.

Il conserve l’expérience complète.

Un analyseur peut reconnaître certaines portions comme lexicales.

D’autres portions peuvent rester initialement sans interprétation.

Si certaines configurations reviennent régulièrement dans des contextes similaires, le moteur d’induction peut créer :

```text

Pattern_713

Pattern_9912

Pattern_44109

```

Ces patterns peuvent ensuite développer leurs propres relations avec :

- des structures lexicales ;

- des changements de structure ;

- des réponses d’autres participants ;

- des positions particulières dans les documents ;

- d’autres patterns appris.

Ce sont ces relations observées qui donnent progressivement une fonction aux structures.

---

## 9.8 Les structures explicites de la source restent des faits de source

Lorsque le format lui-même fournit une structure explicite, elle peut être conservée telle quelle.

Par exemple, si un document source contient un nœud structuré avec un type natif donné, l’Observation Graph peut conserver :

```text

source_node N

source_type = X

```

Le point important est que :

```text

source_type = X

```

signifie :

> la source a fourni X

et non :

> le système cognitif possède nécessairement le concept X.

La distinction entre provenance externe et connaissance interne doit être explicite dans toutes les structures.

---

## 9.9 Pas de feature engineering cognitif à l’entrée

La couche Observation Graph ne doit pas contenir une collection croissante de détecteurs écrits à la main pour des phénomènes particuliers.

Le développement ne doit pas dériver vers :

```text

detect_pattern_A()

detect_pattern_B()

detect_pattern_C()

...

```

lorsque ces patterns correspondent à des abstractions que l’induction pourrait apprendre à partir des observations.

Une transformation déterministe est acceptable lorsqu’elle est nécessaire pour :

- décoder le média ;

- préserver la structure native d’une source ;

- rendre une observation adressable ;

- relier une annotation externe à son support original.

Elle devient suspecte lorsqu’elle affirme déjà la fonction ou la signification d’une configuration particulière.

---

## 9.10 Graphe d’observation versus graphe appris

L’architecture doit maintenir une séparation stricte entre deux espaces.

### Observation Graph

Contient ce qui est directement observable ou explicitement fourni par les sources, ainsi que les liens vers les analyses externes.

Il est principalement :

```text

historique

fidèle à la source

provenance-aware

non destructif

```

### Learned Graph

Contient les structures créées par le système lui-même à partir de l’expérience.

Par exemple :

```text

Pattern_172

Concept_993

Schema_41

Transformation_883

```

Ces objets sont issus de :

```text

récurrence

comparaison

compression

induction

généralisation

spécialisation

fusion

séparation

raisonnement

```

La séparation fondamentale devient donc :

```text

SOURCE

   ↓

OBSERVATION GRAPH

   │

   ├── external analyzer annotations

   │

   ├── source-native structure

   │

   └── raw observable material

   │

   ▼

EPISODES

   │

   ▼

INDUCTION

   │

   ▼

LEARNED GRAPH

```

---

## 9.11 Principe d’immutabilité conceptuelle de l’observation

Une découverte ultérieure ne doit pas réécrire l’histoire.

Si le système découvre après plusieurs milliards d’occurrences qu’un certain motif possède une fonction stable, les anciennes observations ne sont pas remplacées par cette nouvelle interprétation.

On ajoute plutôt un lien :

```text

LearnedPattern_812

    supported_by

        ObservationOccurrence_1

        ObservationOccurrence_2

        ...

```

Cela permet :

- de recalculer les abstractions ;

- de modifier une classification ;

- de fusionner ou séparer des concepts ;

- de comparer plusieurs hypothèses ;

- d’auditer les apprentissages ;

- de conserver la possibilité qu’une ancienne interprétation ait été erronée.

---

## 9.12 Conséquence pour le NLP

Le pipeline NLP change donc de rôle.

Il ne fait plus :

```text

RAW TEXT

   ↓

NLP

   ↓

TRUE INTERNAL REPRESENTATION

```

Il fait :

```text

RAW SOURCE

   ↓

OBSERVATION GRAPH

   ↓

NLP / OTHER ANALYZERS

   ↓

ANNOTATED OBSERVATION GRAPH

```

Puis seulement :

```text

ANNOTATED OBSERVATION GRAPH

   ↓

EPISODIC STORAGE

   ↓

INDUCTION

   ↓

LEARNED GRAPH

```

Le NLP augmente donc la quantité de structure observable disponible pour l’induction.

Il ne définit pas à lui seul les concepts internes.

---

## 9.13 Conséquence pour l’apprentissage du discours

Cette séparation est particulièrement importante pour le discours.

Des phénomènes que nos outils externes n’ont pas de catégorie pour décrire peuvent néanmoins être présents dans l’expérience observable.

Si une certaine configuration de structure, de texte, de position, de participants et de transformations suivantes apparaît fréquemment, le système peut découvrir un pattern même si :

```text

aucun tokenizer ne le nomme

aucune grammaire ne le nomme

aucune taxonomie RST ne le nomme

aucune ontologie humaine ne le nomme

```

C’est une condition nécessaire pour que le système puisse découvrir des abstractions que nous n’avons pas prévues.

---

## 9.14 Invariant architectural

À toute étape, le système doit respecter l’invariant suivant :

> Une information observable ne peut pas disparaître uniquement parce qu’aucun analyseur actuel ne sait quoi en faire.

Et :

> Une annotation produite par un outil externe ne devient jamais automatiquement un concept cognitif interne.

---

---

# 10. Transmission / Provenance Graph : contextualiser l’origine et la transmission de l’information

## 10.1 But

Une information ne doit jamais être mémorisée comme un contenu isolé de son origine.

Le système doit préserver la différence entre :

```text

un contenu

le fait qu’un acteur a produit ce contenu

le contexte dans lequel il l’a produit

la chaîne par laquelle ce contenu est arrivé

les réactions et conséquences observables

la connaissance que le système finit par induire à partir de cette histoire

```

Le principe central est :

> Le contenu transmis et l’histoire de sa transmission sont deux structures distinctes, reliées mais jamais confondues.

Une proposition rencontrée dans un texte ne devient donc jamais automatiquement une connaissance du monde.

Elle devient d’abord une partie d’un épisode de transmission.

---

## 10.2 Pas de score universel de fiabilité

Le système ne doit pas attribuer à une personne, une publication ou un média un nombre global du type :

```text

reliability(source) = 0.82

```

Une telle valeur détruirait plusieurs dimensions importantes :

- dépendance au contexte ;

- dépendance au domaine ;

- évolution dans le temps ;

- relations interpersonnelles ;

- chaînes de citation ;

- réputation locale ;

- erreurs ponctuelles ;

- succès passés ;

- influence sociale ;

- différences entre mémorisation, croyance et comportement.

Le système doit conserver les expériences nécessaires pour que ces régularités puissent être **induites**.

Il pourra éventuellement découvrir qu’une certaine source, dans certains contextes structurels, est souvent associée à des contenus ultérieurement corroborés.

Cette structure doit émerger comme un pattern appris.

Elle ne doit pas provenir d’un attribut `trusted = true`.

---

## 10.3 Un événement de transmission comme unité observable

Lorsqu’un contenu est rencontré, le système crée ou enrichit une structure représentant l’événement de transmission.

Conceptuellement :

```text

TransmissionOccurrence T

    source_context = ...

    producer = ...

    observed_material = ...

    parent_context = ...

    time = ...

    source_links = ...

```

Au départ, cette structure ne prétend pas connaître la fonction sociale ou épistémique de l’épisode.

Elle enregistre ce qui est observable.

Lorsque les analyseurs linguistiques auront produit une ou plusieurs interprétations du contenu, celles-ci pourront être reliées à cette occurrence :

```text

TransmissionOccurrence T

    ↓

InterpretationCandidate I1

TransmissionOccurrence T

    ↓

InterpretationCandidate I2

```

Aucune interprétation candidate ne devient automatiquement vraie.

---

## 10.4 Séparer contenu et transmission

Le système doit pouvoir représenter simultanément :

```text

ContentStructure C

```

et :

```text

TransmissionOccurrence T

```

avec un lien entre les deux.

Cela permet de distinguer :

```text

C existe comme structure de contenu

```

de :

```text

T contient / transmet / évoque C

```

Une même structure de contenu peut être rencontrée dans plusieurs transmissions indépendantes :

```text

T1 -> C

T2 -> C

T3 -> C

```

Le système peut alors apprendre à partir :

- de leur indépendance ;

- de leurs chaînes de provenance ;

- de leurs contextes ;

- de leur chronologie ;

- de leurs conséquences ultérieures.

---

## 10.5 La chaîne de transmission doit rester explicite

Un contenu peut arriver par plusieurs intermédiaires.

Exemple conceptuel :

```text

Observation locale

    ↓

Document A

    ↓

Document B qui cite A

    ↓

Message C qui résume B

    ↓

Utilisateur D qui reproduit C

```

Le système ne doit pas écraser cette chaîne en :

```text

source = D

```

ni en :

```text

source = Document A

```

Il doit conserver le chemin complet lorsqu’il est observable.

Une transmission peut donc pointer vers une autre transmission :

```text

T4 derived_from T3

T3 derived_from T2

T2 derived_from T1

```

Les noms des relations exactes peuvent provenir :

- de la structure native de la source ;

- d’un analyseur externe ;

- d’une hypothèse ;

- d’une structure apprise.

Le graphe doit conserver la provenance de chacune de ces relations.

---

## 10.6 La source d’interface n’est pas nécessairement la source épistémique

Le système ne doit jamais considérer automatiquement que :

```text

plateforme = source de connaissance

```

Un message sur une plateforme peut contenir une observation originale, reprendre une autre personne, citer un document, résumer une étude, reproduire une rumeur, intégrer du contenu fictionnel ou mélanger plusieurs origines.

La plateforme n’est qu’un élément du chemin de transmission.

Le système doit conserver assez de structure pour que l’induction puisse apprendre quelles chaînes de provenance sont pertinentes dans quels contextes.

---

## 10.7 Relations sociales sans ontologie sociale hardcodée

Le système ne doit pas recevoir une taxonomie cognitive fixe de relations telles que :

```text

friend

guru

expert

authority

enemy

celebrity

```

Ces termes peuvent apparaître dans le texte ou être fournis explicitement par une source, mais ils ne doivent pas devenir automatiquement des dimensions internes obligatoires.

Le système conserve plutôt les interactions observables :

```text

frequency of interaction

sequence of exchanges

past agreement/disagreement structures

later corroboration

later contradiction

behavioral consequences

retrieval history

shared contexts

```

À partir de ces expériences, l’induction peut découvrir des structures relationnelles récurrentes.

Nous pourrons éventuellement reconnaître humainement certaines d’entre elles comme ressemblant à de la proximité, de la confiance, du prestige, de l’autorité, de la dépendance ou du rejet.

Mais ces catégories doivent être découvertes, pas imposées.

---

## 10.8 Pas de concept interne obligatoire de « source sûre »

Le système ne doit pas posséder un type cognitif fixe :

```text

TRUSTED_SOURCE

```

Il peut en revanche apprendre des structures comme :

```text

Pattern_18271

conditions:

    source-history structure H

    context structure C

observed consequence:

    transmitted structures are frequently corroborated later

support:

    ...

exceptions:

    ...

```

Dans un autre contexte, la même source peut produire un pattern complètement différent.

La confiance devient donc relationnelle, contextuelle, historique et induite plutôt qu’un attribut global.

---

## 10.9 Fiction, simulation, récit et réalité

Le système ne doit pas utiliser un simple drapeau :

```text

fiction = true

therefore ignore

```

Une source narrative peut contenir simultanément des faits transférables hors de son univers, des structures valides uniquement dans son univers, des comportements sociaux observables, des conventions narratives et des éléments entièrement inventés.

Le système doit conserver le contexte d’appartenance des observations.

Si un ensemble de structures se prédit fortement à l’intérieur d’un contexte mais se transfère mal à d’autres contextes, le moteur peut apprendre cette propriété sans qu’on lui ait fourni une ontologie prédéfinie de la fiction.

La distinction importante est donc la **portabilité empirique des structures entre contextes**, pas un booléen décidé à l’entrée.

---

## 10.10 La provenance peut influencer plusieurs processus différents

Le système ne doit pas supposer qu’une source agit uniquement sur la croyance.

L’histoire de transmission peut devenir prédictive de phénomènes distincts, par exemple :

```text

probabilité de récupération ultérieure

modification d’une structure de croyance

activation attentionnelle

transformation comportementale

réutilisation dans une production future

```

Ces effets ne doivent pas être fusionnés dans une métrique unique.

L’induction doit pouvoir découvrir que certaines provenances ont des effets différents sur différentes dynamiques.

---

## 10.11 Contenu et provenance doivent pouvoir avoir des dynamiques de mémoire distinctes

Le lien :

```text

Content C

    ↔

Transmission T

```

doit être une structure mémorisable distincte de `C` lui-même.

Cela permet que :

```text

activation(C)

```

et :

```text

activation(C ↔ T)

```

évoluent séparément.

Le système peut ainsi conserver une structure de contenu tout en récupérant plus difficilement son origine, ou inversement.

Aucune vitesse de dégradation particulière ne doit être imposée universellement.

Les dynamiques de récupération et d’oubli doivent être mesurables et ajustables par apprentissage.

---

## 10.12 Corroboration et contradiction comme histoire, pas comme verdict instantané

Lorsqu’une transmission ultérieure fournit un contenu compatible ou incompatible avec une transmission précédente, le système ne doit pas simplement recalculer un score de fiabilité.

Il doit créer les relations observées entre épisodes.

Conceptuellement :

```text

T1 -> Interpretation A

T2 -> Interpretation B

A compatible_with B

```

ou :

```text

A conflicts_with B

```

avec leur provenance respective.

L’induction peut ensuite découvrir quelles structures de sources, de contextes et de chaînes de transmission prédisent le mieux les consolidations futures.

---

## 10.13 Effets des relations personnelles

Une interaction provenant d’un acteur fréquemment présent dans l’histoire du système ne doit pas être réduite à :

```text

important_person = true

```

L’histoire elle-même doit rester disponible :

```text

episodes partagés

fréquence d’interaction

types de conséquences observées

récupérations antérieures

changements de comportement

coactivation avec d’autres structures

```

Si cette histoire modifie effectivement la mémorisation, l’attention ou les décisions, ces effets doivent être appris à partir de la distribution des épisodes.

---

## 10.14 Propagation vers les épisodes

Un épisode ne doit donc pas contenir seulement :

```text

contenu analysé

```

Il doit aussi conserver ses liens vers le Transmission / Provenance Graph.

Conceptuellement :

```text

Episode E

    contains observed structures ...

    links to TransmissionOccurrence T

    links to source context S

    links to analysis candidates ...

```

Ainsi, deux épisodes sémantiquement similaires peuvent rester très différents sur le plan de leur histoire de transmission.

---

## 10.15 Propagation vers l’induction

Le moteur d’induction doit pouvoir utiliser les structures de provenance exactement comme les autres dimensions observées.

Il peut découvrir des patterns portant sur :

```text

contenu

source

chaîne de transmission

ordre temporel

structure sociale observée

corroboration ultérieure

contradiction ultérieure

récupération

conséquences

```

Il n’existe pas de règle spéciale disant que la provenance a un poids fixe.

La provenance est une partie du graphe sur laquelle l’induction peut trouver des régularités.

---

## 10.16 Propagation vers le runtime online

Lors d’une interaction online, lorsqu’un contenu est récupéré depuis la mémoire globale, ses liens de provenance pertinents doivent pouvoir être récupérés eux aussi.

Le système peut donc comparer :

```text

contenu actuel

structures déjà connues

historique des transmissions liées

patterns appris sur ces historiques

```

avant de consolider ou d’utiliser une information dans le raisonnement courant.

Le contexte actif n’a pas besoin de charger toute la provenance historique.

Il récupère uniquement les fragments pertinents.

---

## 10.17 Provenance des productions du système lui-même

Toute production générée par le système doit être marquée comme telle dans le Source / Transmission Graph.

Il est essentiel de distinguer :

```text

information observée dans une source externe

```

de :

```text

information produite par le système

```

et :

```text

information inférée par le système

```

afin d’éviter qu’un contenu généré soit réingéré plus tard comme preuve extérieure indépendante.

Les futures interactions peuvent néanmoins servir d’expérience.

Elles gardent simplement une provenance distincte.

---

## 10.18 Invariant architectural

À toute étape, les propositions suivantes doivent rester vraies :

> Un contenu n’est jamais une connaissance simplement parce qu’il a été lu.

> La provenance n’est jamais réduite à un score global de fiabilité.

> Une source n’est jamais résumée définitivement par une catégorie sociale ou épistémique prédéfinie.

> Les effets d’une provenance sur croyance, mémoire, attention et action doivent rester séparables.

> Les régularités utiles relatives aux sources doivent être induites à partir de l’histoire des transmissions.

---

---

# 11. Analyse multimodale

Chaque fragment est envoyé au parseur approprié.

Le texte naturel passe par le pipeline NLP. Même lorsqu’aucun signal audio n’est disponible, une forme écrite peut également produire des **hypothèses phonologiques externes** ; celles-ci sont des analyses dérivées de l’orthographe, pas des observations acoustiques. Si un canal audio est ajouté ultérieurement, ses observations phonétiques restent séparées et peuvent corroborer ou contredire ces hypothèses.

Le code passe par un parseur syntaxique du langage correspondant et produit un AST ou une autre représentation structurée.

Les citations conservent leur auteur, leur source et le fait qu’elles ont été citées par un autre locuteur.

Les tableaux, liens, listes et structures documentaires gardent leurs relations natives.

Toutes ces analyses convergent ensuite vers une représentation commune.

---

# 12. Deep Symbolic NLP

Le texte naturel doit être analysé aussi profondément que possible avant le raisonnement de haut niveau.

Outils envisagés :

```text

ERG / ACE

PyDelphin

Link Grammar

WordNet

VerbNet

PropBank

FrameNet

SemLink

HeidelTime — analyseur temporel de surface externe uniquement

Duckling — analyseur de valeurs/durées externe uniquement

Epitran

PanPhon

OpenFst / Pynini

Phonetisaurus ou autre G2P entraînable lorsque pertinent

SUMO ou ressources ontologiques comparables

```

Ils peuvent fournir segmentation, morphologie, syntaxe, HPSG, MRS/EDS/DMRS, rôles, relations lexicales, temps, coréférence, quantification, portée, connecteurs, etc.

Leur rôle est de fournir des **observations structurées**.

Ils ne définissent pas l’ontologie cognitive finale.

Pour le temps, une contrainte supplémentaire s’applique : HeidelTime, Duckling ou tout outil comparable ne constituent **jamais** le modèle temporel cognitif. Ils peuvent seulement produire des annotations externes attribuées. Toute normalisation calendaire ou horlogère reste une hypothèse ou une ancre de source/provenance et ne remplace jamais les relations temporelles sémantiques conservées par le système.

## 12.1 Open Semiotic Acquisition : principe

Le système ne doit pas posséder un « lexique ouvert » au sens simpliste d’un dictionnaire extensible `forme → sens`. Une forme nouvelle peut participer simultanément à plusieurs relations sur plusieurs plans de représentation.

L’objet fondamental reste l’occurrence observable :

```text
ObservedSpan S
    raw = ...
    source = ...
    producer = ...
    time = ...
```

Autour de cette occurrence, les analyseurs et le moteur de récupération peuvent proposer des structures concurrentes ou complémentaires :

```text
ObservedSpan S
    ├── graphemic analyses
    ├── phonological hypotheses
    ├── morphological analyses
    ├── syntactic analyses
    ├── lexical / semantic candidates
    ├── abbreviation / symbolization candidates
    ├── discourse / pragmatic candidates
    ├── provenance / speaker-context links
    └── learned cross-representation relations
```

Une relation sur un plan n’implique jamais automatiquement l’identité sur les autres plans. Deux formes peuvent être phonologiquement proches mais sémantiquement différentes ; graphiquement proches mais sans relation de sens ; ou partager une fonction conversationnelle sans être lexicalement équivalentes.

Cette couche est appelée **Open Semiotic Acquisition** parce qu’elle permet au système d’acquérir progressivement des relations entre formes, sons, symboles, usages et contextes sans supposer qu’un mot possède une unique entrée canonique.

## 12.2 Exemple contraignant : `io`

Une occurrence :

```text
io
```

ne doit jamais être normalisée immédiatement en `yo`. Le système peut conserver simultanément :

```text
Observation
    raw_form = "io"

Candidate A
    graphemic_form = "io"

Candidate B
    phonological_hypothesis ≈ /jo/
    possible phonological relation to known form "yo"

Candidate C
    alternative segmentation / punctuation relation
    "io" ↔ "i/o"

Candidate D
    retrieval through "I/O"
    existing learned/content structures may connect I/O to input/output

Candidate E
    dialogue-context relation
    occurrence occupies a position structurally similar to prior greeting-like exchanges

Candidate F
    provenance/context relation
    usage may correlate with a particular speaker, technical contexts or other recurrent structures
```

Ces candidats ne sont pas des traductions mutuellement exclusives. Plusieurs peuvent être vrais ou utiles simultanément.

Le système ne reçoit pas une primitive `PUN`, `SLANG`, `TYPO`, `TECH_JOKE` ou `GREETING`. Si la combinaison de plusieurs activations produit régulièrement des conséquences observables particulières, l’induction peut finir par créer une structure interne que nous reconnaîtrions humainement comme un jeu de mots, un idiolecte, un slang ou une convention locale.

## 12.3 Phonologie comme plan d’analyse de premier ordre

La phonologie ne doit pas être réduite à une propriété accessoire d’une entrée lexicale. Elle constitue un plan de représentation externe pouvant relier des formes différentes.

Outils retenus pour POC :

```text
Epitran
    orthographie → IPA / segments phonétiques
    alignements orthographie ↔ segments lorsque disponibles

PanPhon
    segments IPA → traits phonologiques
    distances et comparaisons sur traits

Phonetisaurus ou G2P comparable
    candidats grapheme-to-phoneme entraînables
    lattices / alternatives lorsque utiles
```

Ces outils produisent des **hypothèses phonologiques attribuées**. Pour une forme nouvelle ou volontairement atypique, plusieurs prononciations candidates peuvent coexister. Une transcription dérivée du texte n’est jamais assimilée à une observation audio réelle.

La comparaison phonologique doit pouvoir fonctionner sur des structures de traits plutôt que seulement sur une distance de chaînes. Cela permet de récupérer des formes différentes qui peuvent partager une réalisation ou une proximité sonore.

## 12.4 Transformations formelles et transducteurs finis

Les relations de forme peuvent être représentées avec des formalismes finis explicites.

**OpenFst** fournit les primitives de transducteurs finis pondérés. **Pynini** permet de compiler des grammaires de réécriture, expressions régulières et transformations contextuelles en WFST.

Ils peuvent servir à représenter ou générer des candidats tels que :

```text
io ↔ i/o
gr8 ↔ great
formes avec élision
abréviations
variantes ponctuées
translittérations
transformations grapheme ↔ phoneme
```

Le poids d’un chemin ou la sortie d’un transducteur reste un signal d’analyse. Il ne signifie pas :

```text
les deux formes ont le même sens
```

Il signifie seulement qu’une relation formelle explicitement définie ou apprise relie deux structures candidates.

Les caractères, ponctuations et formes originales demeurent conservés dans l’Observation Graph ; les transducteurs ajoutent des chemins d’analyse sans normalisation destructive.

## 12.5 Retrieval cross-représentation

Une forme nouvelle doit pouvoir déclencher plusieurs recherches indépendantes :

```text
forme graphique similaire
forme phonologique similaire
segmentation alternative
abréviation possible
structure morphologique similaire
structure syntaxique compatible
contexte discursif similaire
conséquence conversationnelle similaire
provenance / locuteur / domaine similaire
```

Ainsi `io` peut récupérer séparément des structures associées à `yo`, `I/O`, `Io` ou d’autres occurrences sans qu’un mécanisme de nearest-neighbour choisisse un gagnant unique.

Les relations sémantiques telles que :

```text
I/O → input/output
```

ne sont pas inventées par le module de similarité graphique. Elles doivent provenir d’analyses lexicales externes, de sources observées, du Learned Graph ou d’un raisonnement traçable.

Le résultat de la couche est donc un **Cross-Representation Bundle** contenant des hypothèses distinctes avec leurs bindings, scores éventuels, producteurs, supports et contradictions.

## 12.6 Incertitude, inconnus et exceptions

Une forme inconnue n’est jamais transformée en catégorie globale `UNKNOWN_WORD` ayant pour seule fonction de signaler l’échec.

Elle reste une observation adressable à laquelle peuvent s’ajouter progressivement des hypothèses.

Chaque hypothèse peut conserver :

```text
producer
formalism / method
source spans
output structure
score if provided
constraints
supporting episodes
contradicting episodes
context distribution
provenance
status / activation
```

Le système ne doit pas chercher à faire disparaître les exceptions. Une généralisation conserve les occurrences qu’elle explique mal. Si plusieurs exceptions partagent une structure, elles peuvent devenir le support d’un nouveau pattern, d’une spécialisation ou d’un split.

Conceptuellement :

```text
Pattern_A
    support = many episodes
    exceptions = E17, E91, E442, ...

recurrent structure among exceptions
    ↓
Pattern_B

then possibly
Pattern_A
    ├── specialization B
    └── other cases
```

L’exception est donc une **source d’apprentissage**, pas un résidu à ignorer.

## 12.7 Acquisition de nouvelles relations lexicales et sémiotiques

À mesure que les occurrences s’accumulent, le moteur d’induction peut apprendre des structures réutilisables reliant plusieurs plans :

```text
form F
    ↔ phonological structure P
    ↔ semantic/contextual structures S1..Sn
    ↔ recurrent dialogue consequences D
    ↔ source/provenance distribution C
```

Le résultat n’a pas besoin de devenir une entrée de dictionnaire unique. Il peut rester un sous-graphe appris avec conditions, variantes, exceptions et dépendances contextuelles.

Dynamic Syntax est particulièrement intéressante à cette frontière parce que sa conception lexicale procédurale et les travaux DS/DS-TTR sur l’apprentissage permettent d’étudier comment de nouvelles formes peuvent acquérir progressivement des contributions interprétatives. Cette capacité doit être évaluée en POC ; elle ne remplace pas le moteur d’induction général.

Une relation apprise peut également rester locale :

```text
forme F
works_like X
only under context C
for speakers / sources matching structure P
```

Le système n’est donc pas obligé d’élever chaque néologisme, idiolecte ou slang au rang de convention linguistique globale.

## 12.8 Invariants de l’acquisition sémiotique ouverte

Les invariants suivants sont obligatoires :

> Une forme observée n’est jamais réécrite par une normalisation ou une correction.

> Une similarité graphique, phonologique ou contextuelle n’implique jamais à elle seule une identité sémantique.

> Plusieurs analyses compatibles peuvent être actives simultanément sur des plans différents.

> Une forme non analysée reste disponible pour le retrieval, l’induction et les analyses futures.

> Toute relation acquise doit rester traçable vers ses observations, analyseurs, transformations et épisodes supports.

> Les catégories humaines telles que « slang », « jeu de mots », « faute volontaire », « abréviation » ou « référence culturelle » peuvent servir à annoter ou inspecter des données, mais ne sont pas des primitives cognitives imposées.

Cette couche constitue le mécanisme général par lequel le système peut absorber des néologismes, usages locaux, graphies créatives, homophonies, allusions, conventions techniques et autres innovations sans agrandir manuellement son catalogue cognitif.

---

# 13. Encapsulation des analyses externes

Toute classification provenant d’un outil externe doit être conservée comme une observation attribuée :

```text

analysis_source = ERG

analysis_type = ...

analysis_value = ...

```

ou :

```text

analysis_source = eRST

candidate_relation = ...

```

ou :

```text

analysis_source = DialogBank_ISO24617_2

candidate_dialogue_function = ...

```

ou :

```text

analysis_source = Coreferee

candidate_reference_chain = ...

```

ou :

```text

analysis_source = Epitran / PanPhon

candidate_phonological_structure = ...

```

ou :

```text

analysis_source = Pynini / OpenFst

candidate_form_transduction = ...

```

ou :

```text

analysis_source = CrossRepresentationRetrieval

candidate_links = [...]

supports = [...]

```

Ces labels de dialogue, chaînes de référence, frontières thématiques ou autres annotations pragmatiques sont soumis au même invariant que les autres analyses externes : ils décrivent ce qu’un outil propose, pas ce que le cerveau symbolique doit obligatoirement croire ou utiliser.

Elle n’est jamais transformée automatiquement en vérité architecturale interne.

Le moteur peut l’utiliser, la combiner, l’ignorer, la contredire ou découvrir une structure plus fine.

---

# 14. Learned Graph

L’architecture articule trois graphes complémentaires.

### Observation Graph

Représentation persistante de l’expérience observable, des structures natives de source et des annotations produites par les analyseurs.

### Transmission / Provenance Graph

Représentation du contexte d’origine, de circulation et de transmission de l’information observable.

### Learned Graph

Représentation des structures que le système a réellement induites.

Le Learned Graph peut contenir des objets internes anonymes tels que :

```text

Pattern_...

Concept_...

Schema_...

Transformation_...

```

Il n’est pas construit directement par ERG, WordNet, RST, un tokenizer ou une taxonomie externe.

Il est construit par les mécanismes d’induction à partir :

```text

Observation Graph

+

épisodes

+

analyses externes

+

statistiques

+

structures déjà apprises

```

La chaîne architecturale correcte devient :

```text

SOURCE

   ↓

SOURCE LAYER

   ↓

OBSERVATION GRAPH

   ↓

EXTERNAL ANALYSES

   ↓

ANNOTATED OBSERVATION GRAPH

   ↓

CROSS-REPRESENTATION HYPOTHESES

   ↓

EPISODES

   ↓

INDUCTION

   ↓

LEARNED GRAPH

   ↓

GLOBAL MEMORY / RETRIEVAL / SOAR

```

Le Learned Graph est révisable.

Ses structures peuvent être :

```text

promoted

merged

split

generalized

specialized

weakened

forgotten

```

sans modifier les observations historiques qui les ont produites.

La provenance relie toujours les structures apprises aux observations et épisodes qui les soutiennent.

---

# 15. Ambiguïté

Une phrase ou un fragment peut générer plusieurs interprétations.

Le système conserve :

```text

Interpretation_A

Interpretation_B

Interpretation_C

```

avec leurs supports, contraintes, contradictions et sources analytiques.

Le contexte futur peut favoriser ou éliminer certaines hypothèses.

L’ambiguïté ne concerne pas uniquement plusieurs interprétations d’une phrase. Une même occurrence peut également posséder des analyses simultanées sur des dimensions différentes, sans qu’elles soient mutuellement exclusives.

Par exemple, `io` peut conserver à la fois une hypothèse phonologique liée à `yo`, une hypothèse graphique liée à `I/O`, des liens sémantiques récupérés via cette dernière structure et une fonction interactionnelle induite depuis son contexte. Le système ne doit pas forcer ces dimensions dans un unique `sense_id`.

L’incertitude doit donc pouvoir porter sur :

```text
segmentation
pronunciation
morphology
syntax
reference
lexical relation
semantic interpretation
discourse attachment
pragmatic effect
cross-representation association
```

## 15.1 Gestion factorisée des hypothèses : principe général

L’architecture ne doit pas représenter l’incertitude en clonant un monde complet pour chaque combinaison possible. Une ambiguïté locale doit rester locale aussi longtemps que possible.

Le principe est :

> **Conserver maximalement les possibilités locales, mais matérialiser minimalement leurs combinaisons globales.**

En anglais, pour les commentaires de code ou les documents de conception :

> **Maximal analytical preservation, minimal combinatorial materialization.**

Une occurrence telle que `io` peut donc porter simultanément plusieurs ensembles d’hypothèses :

```text
ObservedForm(io)

phonology:
    P1 -> /jo/
    P2 -> autre réalisation candidate

graphical relations:
    G1 -> similarity(io, I/O)
    G2 -> similarity(io, yo)

semantic / cultural retrieval:
    S1 -> structures liées à I/O / input-output
    S2 -> structures liées à yo

dialogue function:
    D1 -> fonction de salutation candidate
    D2 -> autre fonction candidate
```

Le système ne crée pas automatiquement le produit cartésien `P × G × S × D`. Les candidats demeurent factorisés et reliés par des contraintes de compatibilité, de conflit, de support ou de dépendance.

## 15.2 Hypothèse, justification et sélection historique

Une hypothèse est un objet persistant distinct de l’observation qui l’a déclenchée et distinct d’une décision temporaire prise par le runtime.

Conceptuellement :

```text
Hypothesis H
    target_structure = ...
    relation = ...
    supported_by = [...]
    contradicted_by = [...]
    depends_on = [...]
    conflicts_with = [...]
    provenance = [...]
    outcome_history = [...]
```

Une sélection à l’instant `t` est un événement séparé :

```text
SelectionEvent S_t
    episode = E_t
    candidates_considered = [H1, H2, H3]
    selected = H1
    decision_context = Context_t
```

Si l’expérience future favorise H2, l’architecture ne réécrit jamais `SelectionEvent S_t`. Elle ajoute de nouvelles justifications et de nouveaux événements de sélection.

Le système peut ainsi apprendre simultanément :

```text
ce que la forme semble signifier / accomplir
+
quelles stratégies d’interprétation avaient auparavant réussi ou échoué
```

## 15.3 Graphe de justifications et maintien de vérité

La gestion des alternatives doit s’inspirer des **Truth Maintenance Systems** et plus particulièrement de l’idée d’**Assumption-Based Truth Maintenance System (ATMS)** : conserver explicitement les dépendances entre conclusions, hypothèses et justifications afin de pouvoir raisonner avec plusieurs contextes incompatibles sans rétracter destructivement les données qui les ont produits.

L’architecture n’adopte toutefois pas naïvement l’énumération exhaustive de tous les environnements d’un ATMS classique, car cette énumération peut elle-même devenir combinatoire. Elle retient surtout les principes suivants :

```text
justification graph
assumption dependencies
explicit contradictions / nogoods
shared sub-results across alternatives
non-destructive revision
context-sensitive activation
```

Les contradictions connues doivent être représentables comme contraintes explicites :

```text
H1 conflicts_with H7
H2 requires H4
H3 supported_by Episode_912
H3 contradicted_by Episode_1804
```

Z3 peut être utilisé pour tester localement la compatibilité d’un ensemble d’hypothèses lorsqu’une combinaison doit réellement être matérialisée. Le graphe de justifications, lui, reste stocké dans la représentation structurelle commune.

## 15.4 Evidence Ledger : pondération sans vérité scalaire permanente

Une hypothèse ne doit pas être résumée définitivement par une unique probabilité globale. Le système conserve plutôt un **Evidence Ledger** inspectable.

```text
EvidenceLedger(H)
    direct_support
    direct_contradiction
    contextual_support
    structural_fit
    phonological_fit
    semantic_fit
    discourse_fit
    speaker_specific_history
    provenance_patterns
    downstream_outcomes
    complexity_cost
    recency / stability statistics
```

Pour sélectionner les hypothèses actives dans un contexte donné, un ranking contextuel peut combiner ces dimensions :

```text
rank(H | current_context) =
    learned_weighted_evidence(H, current_context)
    - contradiction_cost
    - description / complexity cost
```

Les poids peuvent eux-mêmes être appris et varier avec le contexte. Le résultat de ce ranking est un **outil de sélection runtime**, pas une nouvelle vérité inscrite dans l’Observation Graph.

## 15.5 Révision incrémentale et apprentissage après erreur

Supposons une première occurrence :

```text
t1: io

H1 = typo accidentelle
H2 = relation fonctionnelle / phonologique avec yo
H3 = relation graphique / culturelle avec I/O
```

Le runtime peut sélectionner H1. L’épisode conserve cette sélection et la réponse produite.

Des épisodes ultérieurs peuvent produire :

```text
io -> réponse de salutation
io mon gars -> réponse de salutation
io dans un contexte informatique -> activation supplémentaire de structures I/O
```

Le système ajoute alors des supports à H2 et H3, et éventuellement des contre-exemples à H1. Lors d’une occurrence future, le ranking peut favoriser H2 et H3 sans supprimer H1 ni falsifier l’histoire de `t1`.

Une correction explicite de l’utilisateur constitue elle aussi une observation avec provenance :

```text
user_correction
    supports H2
    contradicts selected_at_t1(H1)
    outcome_for_strategy = poor
```

Cette structure permet d’apprendre les objets linguistiques **et** les stratégies d’interprétation.

## 15.6 Composition paresseuse des interprétations

Une interprétation globale n’est construite que lorsqu’un raisonnement, une contrainte ou une décision en a besoin.

Si le système possède :

```text
3 candidats phonologiques
4 candidats sémantiques
3 candidats pragmatiques
2 candidats référentiels
```

il ne doit pas stocker immédiatement `3 × 4 × 3 × 2 = 72` interprétations complètes.

Il conserve :

```text
P = {P1, P2, P3}
S = {S1, S2, S3, S4}
D = {D1, D2, D3}
R = {R1, R2}

+ compatibility / conflict constraints
+ justifications
```

Lorsque le runtime a besoin d’une interprétation cohérente, il demande au gestionnaire d’hypothèses de produire quelques assemblages pertinents. Les parties communes sont partagées par référence plutôt que copiées.

Cette politique s’applique également aux ambiguïtés de portée, d’attachement syntaxique, de coréférence, de discours et d’état conversationnel.

## 15.7 Beam actif borné et diversité structurelle

Soar ne doit jamais recevoir toutes les possibilités persistantes. Le runtime récupère un **beam actif borné**.

Exemple conceptuel :

```text
active_beam.max = 16

12 candidats les mieux supportés
+
3 candidats représentant des familles structurelles différentes
+
1 candidat novelty / outlier
```

Les nombres exacts sont configurables et doivent être évalués expérimentalement ; ils ne constituent pas une théorie cognitive.

La diversité est importante : un simple top-k scalaire peut éliminer trop tôt une famille d’explications encore faiblement supportée mais structurellement différente. Le beam doit donc utiliser à la fois le ranking et une contrainte de diversité / couverture des familles d’hypothèses.

## 15.8 Partage structurel, déduplication et stockage compact

Une hypothèse ne copie pas les structures qu’elle référence.

Mauvais modèle :

```text
Hypothesis_1
    full copy of YO structure
    full copy of I/O structure
    full copy of context
```

Modèle attendu :

```text
Hypothesis_1
    source_occurrence_id = ...
    relation_id = ...
    target_structure_id = ...
    justification_ids = [...]
```

Des milliers d’occurrences soutenant une même relation doivent converger vers une structure partagée :

```text
HypothesisPrototype_77
    support_count = ...
    contradiction_count = ...
    context_statistics = ...
    occurrence_postings = compressed references
```

Les épisodes détaillés restent disponibles dans le stockage historique, tandis que les index rapides peuvent utiliser des agrégats, IDs et statistiques suffisantes.

## 15.9 Stockage froid et pruning réversible

Une hypothèse devenue peu utile ne doit pas nécessairement rester dans les index chauds.

```text
active / hot
    ↓
warm
    ↓
cold / archived
```

Le passage vers le stockage froid peut dépendre de métriques générales comme :

```text
faible support
forte contradiction
faible utilité de retrieval
absence d’activation récente
redondance avec une structure plus compacte
coût d’indexation
```

Mais :

> **Archiver une hypothèse ne doit jamais supprimer les observations qui permettraient de la reconstruire.**

Le pruning est donc principalement un retrait des index actifs ou une compression de la structure dérivée, pas une destruction des traces historiques.

## 15.10 Invariants de la gestion d’incertitude

Les invariants suivants s’ajoutent aux invariants généraux de l’architecture :

> Une hypothèse sélectionnée n’est pas une vérité permanente.

> Une hypothèse rejetée aujourd’hui peut redevenir pertinente demain si le contexte ou les observations changent.

> Les alternatives locales sont représentées indépendamment tant qu’une dépendance réelle ne justifie pas leur composition.

> Le produit cartésien des ambiguïtés ne doit jamais être matérialisé par défaut.

> Les parties communes de plusieurs interprétations doivent être partagées structurellement.

> Toute révision doit rester traçable jusqu’aux nouvelles observations, contraintes ou outcomes qui l’ont provoquée.

> La mémoire de travail est strictement bornée ; les mémoires cognitives des
> systèmes restent principalement en RAM, avec checkpoint coordonné et
> déplacement froid réversible lorsque la pression l'exige.

> Une réduction de coût de stockage ne doit jamais transformer l’oubli d’une hypothèse dérivée en falsification de l’expérience originale.

## 15.11 Worked lifecycle — réinterprétation d’une forme inconnue dans le temps

Ce scénario sert de test d’intégration pour la gestion factorisée des hypothèses. Il n’ajoute aucune catégorie cognitive hardcodée.

### t1 — première occurrence

Le 1er mai, le système observe `io`. L’Observation Graph conserve la forme brute et son contexte. Les analyseurs produisent plusieurs hypothèses locales, par exemple :

```text
H1  faute / variation accidentelle
H2  relation phonologique avec "yo"
H3  relation graphique ou culturelle avec "I/O"
H4  forme indépendante encore inconnue
```

L’Evidence Ledger relie chaque hypothèse à ses supports, contradictions et contexte. Le ranking courant peut sélectionner `H1`. L’épisode doit alors conserver explicitement :

```text
observation = OBS_t1
candidates = {H1,H2,H3,H4}
selected_at_time = H1
evidence_snapshot = EV_t1
```

Les hypothèses non sélectionnées ne sont pas supprimées.

### Entre t1 et t2 — nouvelles données et induction

De nouvelles conversations peuvent fournir : récurrence de formes similaires, conséquences conversationnelles, relations phonologiques ou graphiques, historique du même locuteur et nouveaux patterns induits. Le moteur peut par exemple découvrir un pattern anonyme reliant une déformation de surface à une fonction interactionnelle conservée.

Ces nouvelles structures peuvent ensuite créer des liens rétrospectifs vers `OBS_t1` sans modifier l’observation ni prétendre que le système les connaissait à t1.

### t2 — seconde occurrence

Le 2 mai, une nouvelle occurrence `io` crée `OBS_t2`. Les hypothèses locales sont produites de nouveau, mais le retrieval peut maintenant récupérer :

```text
OBS_t1
Evidence Ledger antérieur
patterns appris entre t1 et t2
historique du locuteur
structures liées à "yo"
structures liées à "I/O"
outcomes des épisodes précédents
```

La répétition de la même forme par le même locuteur dans un contexte compatible peut constituer une nouvelle évidence contre l’hypothèse d’une faute purement accidentelle. Les relations phonologiques, graphiques et interactionnelles peuvent simultanément soutenir d’autres hypothèses.

Le ranking actif est alors recalculé à partir du nouveau graphe d’évidence. Une hypothèse ou une composition paresseuse différente peut être sélectionnée à t2.

```text
t1: selected_at_time = H1
t2: selected_at_time = compose(H2,H3,Pattern_X)
```

Le système a donc changé d’interprétation parce que **les données disponibles et leurs relations ont changé**, non parce que l’épisode t1 a été réécrit.

### Invariant du lifecycle

> Une nouvelle observation peut modifier le ranking présent, créer de nouveaux patterns et réévaluer d’anciennes hypothèses, mais elle ne peut jamais modifier ce qui avait été observé, envisagé ou sélectionné historiquement.

---

# 16. Épisodes

L’unité fondamentale de l’ingestion offline est l’épisode.

Un épisode contient un fragment cohérent d’expérience avec :

```text

source graph fragment

semantic analyses

graphemic / phonological / form-transduction analyses

cross-representation hypotheses and their supports

factorized hypothesis IDs / justification edges / contradiction edges

selection events (`selected_at_time`) and active-beam snapshot when relevant

evidence-ledger snapshot or deltas relevant to the episode

links to later corrections / outcomes without rewriting the original episode

participants

observable order / temporal-relation candidates / episodic temporal context

external clock/calendar anchors when supplied by the source, kept as provenance only

document context

reply structure

code structures

candidate discourse analyses

formal dialogue analyses (DS / ISO / SDRT / KoS-TTR)

information-state update candidates and accepted interaction-state deltas

QUD / grounding / obligations / unresolved bindings

response-plan traces when the system is a participant

observable outcomes

```

Un épisode n’est pas une généralisation.

Il est une trace historique.

---

# 17. Mémoire épisodique

La mémoire épisodique conserve les expériences spécifiques.

Elle doit permettre des recherches par :

```text

partial graph match

shared graphemic / phonological / symbolic structure

cross-representation links

shared structure

shared constraints

source relationships

temporal relationships

linked entities

linked induced patterns

```

Les expériences originales restent accessibles même si les abstractions dérivées changent ou disparaissent.

## 17.1 Refonte temporelle : statut

La couche temporelle est un **substrat transversal** de la mémoire et du raisonnement. L’architecture fixe ses invariants, mais considère sa théorie computationnelle détaillée comme encore provisoire tant que l’étude formelle linguistique, psychologique et neuroscientifique n’est pas terminée.

HeidelTime, Duckling et les timestamps de source ne doivent donc pas être implémentés comme « le temps du système ».

## 17.2 Temporal Relationality Invariant

> Toute information temporelle cognitive doit être représentée principalement par des relations entre événements, états, observations, épisodes ou contextes. Les coordonnées calendaires ou horlogères externes peuvent être conservées uniquement comme ancres de provenance et ne doivent jamais remplacer les relations temporelles à partir desquelles elles ont été obtenues.

La représentation privilégiée ressemble à :

```text
Event_A
    temporal_relation → Event_B

Observation_X
    contained_in → Episode_Y

Episode_Y
    temporal_relation → Episode_Z

State_S
    validity_relation → Context_I
```

Les noms humains de relations montrés dans les exemples ne constituent pas nécessairement une enum cognitive interne. Les structures internes peuvent rester anonymes et apprises.

## 17.3 No Temporal Normalization Collapse

Une expression comme :

```text
hier
avant
après
plus tard
encore
déjà
toujours
depuis
jusqu'à
pendant
venir de
être sur le point de
continuer à
cesser de
```

ne doit jamais être réduite irréversiblement à une coordonnée normalisée. Sa forme, son contexte, ses analyses, ses relations candidates, ses ambiguïtés et sa provenance restent disponibles.

Un résultat externe tel que :

```text
"hier" -> 2024-05-22
```

peut être conservé comme annotation attribuée si un analyseur le produit, mais ne remplace jamais la structure relationnelle de l’expression dans le discours.

## 17.4 Temporalités distinctes

Le système doit pouvoir distinguer sans les confondre :

```text
temps de l'événement décrit
temps de référence dans le discours
temps de l'énonciation
temps d'observation par le système
temps de transmission
temps d'intégration dans un épisode
temps de rappel
ordre entre épisodes
distance contextuelle ou temporelle relative
```

Par exemple :

```text
Hier, Julie m'a dit que Paul partirait demain.
```

peut contenir plusieurs relations temporelles imbriquées qui ne se réduisent pas à une seule date.

## 17.5 Quatre niveaux de représentation temporelle

### 17.5.1 Ordre observable

Conserver sans théorie supplémentaire l’ordre ou les relations explicitement fournis par l’expérience ou la source :

```text
Observation_A -> Observation_B
Message_17 reply_to Message_12
Turn_3 precedes_in_source Turn_4
```

Les timestamps éventuels restent des métadonnées de source.

### 17.5.2 Sémantique temporelle du discours

Les formalismes linguistiques peuvent produire des **relations temporelles candidates** et des structures de tense, aspect, référence temporelle ou anaphore. Les familles théoriques à étudier incluent notamment DRT / Temporal DRT, SDRT, Reichenbach, event semantics, aspectual semantics, temporal anaphora et temporal discourse relations.

Ces sorties restent encapsulées comme analyses externes :

```text
analysis_source = temporal_formalism_adapter
candidate_temporal_structure = ...
```

Aucun label externe ne devient automatiquement une primitive cognitive.

### 17.5.3 Contexte temporel épisodique

La mémoire doit pouvoir reconstruire une position temporelle à partir de l’organisation de l’expérience :

```text
Episode_88
    contains -> Observation_X

Observation_X
    related_to -> Observation_W
    related_to -> Observation_Y
    same_local_context -> Context_31

Context_31
    succeeds -> Context_30
    precedes -> Context_32
```

La proximité temporelle peut émerger de la structure des séquences, de la continuité contextuelle, des frontières d’événements et des transitions entre épisodes.

### 17.5.4 Structures temporelles apprises

Les catégories temporelles cognitives ne doivent pas être une enum fermée comme :

```text
BEFORE AFTER DURING OVERLAPS UNTIL SINCE STILL ALREADY AGAIN ...
```

Même une algèbre temporelle formelle utile ne devient pas automatiquement l’ontologie interne. Le Learned Graph peut créer des Pattern_..., Schema_... et Transformation_... anonymes à partir des régularités observées.

## 17.6 Le temps comme pouvoir relationnel des formes linguistiques

Les expressions temporelles peuvent agir sur des structures déjà actives : référence d’événement, persistance, répétition, frontière, ordre, aspect, présupposition temporelle ou changement d’état.

Le système ne doit pas coder manuellement une fonction par terme. Il doit utiliser les structures linguistiques formelles et l’induction pour apprendre les régularités de leurs effets.

## 17.7 Ancres absolues strictement séparées

Lorsqu’une source fournit une date ou une heure, elle peut créer :

```text
ExternalClockAnchor
ExternalCalendarAnchor
SourceTimestamp
DocumentCreationTime
```

Ces objets appartiennent au Source Graph et/ou au Transmission / Provenance Graph. Ils peuvent être reliés à des épisodes et utilisés pour répondre à une question calendaire précise, mais ils ne structurent pas à eux seuls la mémoire temporelle cognitive.

Exemple :

```text
ExternalClockAnchor_17
    source = message_metadata
    value = 2024-05-23T11:10:12
    anchors -> TransmissionOccurrence_918
```

## 17.8 Exemple cible : « quand est-ce que j'ai entendu ça ? »

La récupération doit d’abord traverser les relations d’expérience :

```text
P
 ↓
TransmissionOccurrence_918
 ↓
Episode_B

Episode_B
    after/relative-to -> Episode_A
    before/relative-to -> Episode_C
```

La première reconstruction peut donc être :

```text
après la discussion avec Julie et avant mon départ au travail
```

Si une ancre externe est également disponible, elle peut ensuite permettre une réponse calendaire plus précise sans remplacer la reconstruction relationnelle.

## 17.9 Fondations scientifiques à établir avant implémentation définitive

La conception détaillée doit être précédée d’une étude systématique de quatre familles :

```text
FORMAL LINGUISTICS
    DRT / Temporal DRT
    SDRT
    Reichenbach
    tense / aspect / event semantics
    temporal anaphora / reference time

PSYCHOLOGY
    episodic memory
    temporal context models
    event segmentation
    sequence memory
    duration / temporal distance
    contextual drift / reconstruction

NEUROSCIENCE
    hippocampus
    time cells
    entorhinal representations
    sequence/context coding
    replay
    event boundaries
    multi-scale temporal representation

FORMAL COMPUTATION
    relation graphs
    constraint propagation
    interval reasoning
    state persistence
    temporal uncertainty
    partial ordering
    incremental / lazy temporal composition
```

La neuroscience et la psychologie servent à contraindre et inspirer l’architecture ; elles ne justifient pas automatiquement une primitive symbolique particulière.

## 17.10 Grille obligatoire d’évaluation des mécanismes temporels

Chaque mécanisme proposé doit documenter :

```text
source théorique ou empirique
ce qu'il affirme exactement
données en entrée
structure produite
niveau de certitude
catégories hardcodées nécessaires
relations hardcodées nécessaires
compatibilité avec l'induction
compatibilité Observation Graph / Learned Graph
risque de contamination ontologique
acceptable / rejeté / à étudier
```

Aucun mécanisme temporel ne doit entrer dans le cœur cognitif sans cette analyse.

## 17.11 Statut de HeidelTime et Duckling

HeidelTime et Duckling sont reclassés comme **External Temporal Surface Analyzers**. Ils peuvent fournir spans, durées, intervalles, grains, valeurs ou normalisations candidates, mais leurs sorties restent attribuées à leur producteur et ne deviennent jamais le modèle temporel interne.

Un outil temporel est rejeté si sa réduction en valeur canonique ne peut pas être isolée de la représentation cognitive.

## 17.12 Prudence scientifique

L’architecture ne suppose pas que le cerveau « ne stocke jamais de temps absolu ». Elle retient plutôt que les données cognitives disponibles motivent l’étude de la séquence, du contexte, de l’ordre, des événements, de la durée, des transitions et de représentations multi-échelles.

La priorité donnée à la représentation relationnelle est donc un choix architectural contraint par ces données, pas une prétention de reproduire exactement le mécanisme neuronal.

---

# 18. Mémoire globale

La mémoire globale est un ensemble de mémoires vivantes, principalement en RAM,
indépendantes de la working memory de Soar. Les checkpoints, le journal de
reprise et le stockage froid rendent leur état persistant sans transformer une
base de données en cerveau actif.

Elle contient :

```text

raw source references

source graphs

episodes

analysis graphs

phonological / form-analysis graphs

cross-representation hypothesis links

factorized hypothesis prototypes

justification / contradiction / dependency graph

evidence ledgers and context-conditioned statistics

selection-event history

archived / cold hypotheses and reconstruction pointers

induced structures

statistics

cross-links

provenance

indexes

```

Sa limite pratique doit être principalement le stockage et les performances d’indexation.

---

# 19. Soar

Soar n’est pas le datastore universel.

Soar sert au runtime cognitif actif :

```text

working memory

goal management

retrieval control

procedural learning

chunking

episodic access

semantic access

decision cycle

```

La mémoire globale externe fournit à Soar uniquement les éléments actifs nécessaires au raisonnement courant.

Pour l’incertitude, cette frontière est stricte : Soar reçoit uniquement un **beam actif borné** d’hypothèses ou d’interprétations matérialisées, accompagné des contraintes et justifications nécessaires au raisonnement courant. Les alternatives persistantes non actives restent dans le gestionnaire d’hypothèses externe.

## 19.1 Runtime continu, graphe de services et reprise

Le runtime n'est ni la suite des scripts de POC, ni une chaîne qui relit leurs
répertoires `output`. Les POC valident des capacités; en exécution, les systèmes
échangent des artefacts cognitifs typés selon le blueprint
`plans/cognitive_system_architecture.json`. Les contrats, couches, mémoires et
flows sont détaillés dans `plans/architecture_runtime_cognitif.md`.

Dans une vague de traitement, la matière monte effectivement des niveaux bas
vers les niveaux hauts : source → observation immuable → analyses formelles
parallèles → adaptateurs → correspondances → sémantique, référence et
temporalité → hypothèses → dialogue/discours → situation et épisodes →
induction → concepts et scripts appris. En mode chatbot seulement, le retrieval
sur ces mémoires internes alimente Soar, les transformations, la planification
et la réalisation.

Les Parquet ne sont jamais interrogés par Soar et ne constituent pas une base
de réponses. En ingestion, une question puis une réponse Stack Overflow sont
deux observations successives du même environnement discursif. Chacune suit le
même chemin bottom-up. La relation source `parent` reste un fait de source;
toute relation sémantique « répond à » doit être construite par les systèmes de
dialogue et de discours, puis évaluée hors du runtime contre les annotations.

Une demande d'évaluation n'est pas encore une mise à jour d'état. Le runtime
matérialise plusieurs transformations inspectables avec préconditions, effets
et justifications. Soar les reçoit comme opérateurs concurrents. L'application
sélectionnée produit un nouvel état réversible dans une vague ultérieure. Des
conversations indépendantes possèdent des contextes de décision indépendants.

Le processus conserve en RAM les mémoires propriétaires des systèmes, le
Learned Graph, les épisodes, les hypothèses factorisées, les indexes et le
Control State. La working memory Soar reste une projection active beaucoup plus
petite. Les seuils de propagation, la profondeur maximale, les budgets et la
diversité du beam vivent dans le Control State; les limites physiques de sûreté
restent extérieures et infranchissables. Le corpus brut demeure sur disque et
n'entre jamais intégralement en mémoire active.

La reprise après arrêt est un **checkpoint coordonné du système**, pas seulement
un fichier Soar. Sur l'installation retenue, `save agent` couvre les productions,
la mémoire sémantique et des réglages; les mémoires sémantique et épisodique ont
aussi leurs sauvegardes de base. Cette capacité ne suffit pas à affirmer que la
working memory courante est restaurée intégralement. Le checkpoint doit donc
conserver également Active Context, beam, buts et opérateurs exposés, références
externes, watermarks des stores, travaux en vol, offset du journal d'entrée et
graine aléatoire. La restauration recharge les stores et l'état Soar
sauvegardable, reconstruit la WM depuis l'Active Context attribué, rejoue
uniquement les événements postérieurs au watermark, puis compare l'état et la
décision obtenus à ceux précédant l'arrêt.

OpenRouter et les manifestes d'attentes appartiennent exclusivement au plan
d'évaluation des POC. Ils peuvent comparer une trace produite à une attente
sémantique difficile à formaliser, mais leur verdict n'entre jamais dans la
mémoire cognitive, le ranking, Soar ou le chemin de production.

---

# 20. Grand Contexte Global

Le système ne charge jamais tout le corpus en mémoire active.

```text

GLOBAL MEMORY

    ↓

retrieval

    ↓

FACTORIZED HYPOTHESIS MANAGER

    ↓

lazy composition + bounded diverse beam

    ↓

ACTIVE CONTEXT

    ↓

WORKING MEMORY

```

La sélection peut utiliser des métriques générales comme :

```text

structural similarity

graph connectivity

recent activation

frequency

current constraints

unresolved variables

current goals

retrieval history

provenance relevance

```

Aucune catégorie métier particulière n’est nécessaire.

---

# 21. Induction Engine

Le moteur d’induction est le cœur du projet.

Il cherche dans les épisodes et structures existantes :

```text

repeated subgraphs

recurring transformations

stable co-occurrences

conditional regularities

structural equivalences

shared constraints

compressible patterns

reusable transformations

```

Il produit de nouvelles structures internes.

Le moteur d’induction participe aussi à la consolidation des hypothèses : des liens locaux répétés peuvent devenir des prototypes partagés ; des familles d’hypothèses peuvent être fusionnées, spécialisées ou séparées ; et les résultats de sélection suivis d’outcomes observables peuvent modifier les stratégies de ranking futures. L’induction ne doit toutefois pas convertir une forte fréquence en vérité rétroactive sur les épisodes passés.

---

# 22. Structures induites

Une structure induite peut être enregistrée anonymement :

```text

Pattern_8721

matches:

  graph shape G

context:

  constraints C1..Cn

observed consequences:

  ...

support:

  ...

exceptions:

  ...

utility:

  ...

```

Nous pouvons éventuellement lui donner un nom humain pour l’inspection, mais le nom n’a aucun rôle cognitif nécessaire.

---

# 23. Induction récursive

Les abstractions deviennent elles-mêmes des observations possibles pour les niveaux suivants.

```text

raw episodes

    ↓

Pattern_1

Pattern_2

Pattern_3

    ↓

Pattern_900

    ↓

Schema_12

    ↓

Schema_144

```

Le système doit pouvoir découvrir des motifs de motifs et des abstractions d’abstractions.

C’est cette récursivité qui doit produire la montée en généralité.

---

# 24. Promotion, fusion, séparation et oubli

Une structure candidate n’est pas automatiquement permanente.

Sa valeur peut être évaluée par des métriques générales :

```text

support

compression gain

cross-context recurrence

prediction improvement

retrieval usefulness

reasoning reuse

description cost

exception rate

stability over time

```

Deux structures peuvent être fusionnées si elles deviennent redondantes.

Une structure peut être divisée si elle recouvre plusieurs comportements incompatibles.

Une structure peu utile peut perdre de l’activation ou être oubliée comme abstraction, tout en conservant ses épisodes d’origine.

Pour les hypothèses, « oubli » signifie en priorité retrait des index chauds, agrégation ou passage en stockage froid. Les références minimales nécessaires à la reconstruction et les observations sources restent conservées conformément au principe de révision non destructive.

---

# 25. Compression hiérarchique

Le système ne doit pas seulement accumuler des faits.

Il doit transformer une masse d’expériences en structures plus compactes :

```text

millions d’épisodes

      ↓

motifs récurrents

      ↓

abstractions réutilisables

      ↓

abstractions de plus haut niveau

```

La compression doit améliorer la réutilisation et le raisonnement sans perdre la provenance.

---

# 26. Formal Concept Analysis

La FCA peut être utilisée comme un mécanisme de découverte.

Elle doit rester :

```text

incremental

pruned

utility-driven

disk-aware

```

Elle ne doit pas construire toutes les combinaisons possibles ni imposer une ontologie.

---

# 27. Inductive Logic Programming

L’ILP peut produire des règles symboliques à partir de structures observées.

Les prédicats utilisés par ces règles peuvent eux-mêmes référencer des concepts ou patterns induits.

Ainsi, même si la règle finale est logique et inspectable, son vocabulaire n’a pas besoin d’être prédéfini manuellement.

---

# 28. Statistiques

Le système peut accumuler des statistiques massives :

```text

frequency

conditional frequency

transition counts

co-occurrence

support

counterexamples

context distribution

stability

outcome correlation

```

Les statistiques guident l’induction, la récupération et la sélection.

Elles ne nécessitent pas de réseau neuronal.

---

# 29. Discours : même philosophie que le reste

Le discours ne reçoit aucune ontologie cognitive prédéfinie.

RST, eRST, SDRT et autres formalismes deviennent des **capteurs analytiques**.

Ils fournissent :

```text

external analyses

candidate relations

structural hints

annotation features

```

Le moteur d’induction reste libre de découvrir d’autres découpages et d’autres structures.

---

# 30. RST/eRST/SDRT comme features, jamais comme cerveau

Si eRST propose une relation X entre deux segments :

```text

analysis_source = eRST

candidate_relation = X

```

Le système peut découvrir que ce label externe recouvre plusieurs patterns internes différents.

Il peut aussi découvrir des patterns sans équivalent RST.

Les catégories des formalismes externes ne définissent donc pas l’espace des abstractions possibles.

---

# 31. Apprentissage discursif

À partir de corpus conversationnels, le système observe notamment :

```text

speaker transitions

reply links

semantic changes

focus shifts

thread topology

source-side outcomes

temporal structure

changes in active constraints

```

Il cherche des sous-graphes et transformations récurrents.

Exemple purement structurel :

```text

ContextGraph_A

   ↓

Transformation_17

   ↓

OtherParticipantOutput

   ↓

ContextGraph_B

```

Après répétition, cette séquence peut devenir :

```text

Pattern_8821

```

puis participer à des abstractions plus hautes.

---

# 32. Aucune enum de capacités conversationnelles

Le système ne choisit jamais dans une liste prédéfinie de comportements conversationnels.

Des termes humains tels que « question », « réponse », « explication » ou « plaisanterie » peuvent exister :

- dans les annotations d’un corpus ;

- dans une analyse linguistique ;

- comme labels ajoutés par un humain pour inspecter un pattern.

Ils ne sont pas des primitives obligatoires de l’espace d’action.

---

# 33. Forme linguistique versus fonction

Le NLP peut observer qu’une phrase possède une certaine structure grammaticale.

Par exemple :

```text

surface_feature = interrogative_form

```

Cela ne signifie pas que le système impose ensuite une fonction cognitive correspondante.

La fonction d’une construction est apprise à travers ses usages réels, ses contextes et ses conséquences observées.

---

# 34. Analyse conversationnelle : une couche linguistique formelle, pas une boîte à outils de chatbot

La conversation doit être traitée avec la même exigence que la grammaire de phrase.

ERG/HPSG/MRS ne sont pas retenus parce qu’ils sont pratiques, mais parce qu’ils implémentent des formalismes linguistiques explicites et produisent des structures interprétables. La couche conversationnelle doit suivre le même principe.

Elle ne doit donc pas être construite autour d’une collection de features utilitaires telles que :

```text
prompt_type
politeness_score
reply_similarity
topic_shift_score
```

Ces mesures peuvent être utiles pour l’exploration de corpus, mais elles ne constituent pas une théorie de la conversation.

La chaîne recherchée est plutôt :

```text
observation du tour
        │
        ├──────────────► analyse grammaticale / sémantique de phrase
        │                ERG / HPSG / MRS / EDS / DMRS
        │
        ├──────────────► analyse incrémentale de l’énoncé
        │                Dynamic Syntax / DyLan
        │
        ▼
cross-representation bundle
orthography / phonology / lexical / symbolic candidates
        │
        ▼
bundle d’interprétations de l’énoncé
        │
        ├──────────────► fonction communicative candidate
        │                DIT++ / ISO 24617-2 / DiAML
        │
        ├──────────────► structure discursive inter-tours
        │                SDRT
        │
        ▼
contexte dialogique formalisé
KoS / TTR / Dialogue Gameboard
        │
        ▼
candidats de mise à jour
Information State Update
        │
        ├── grounding
        ├── questions ouvertes / QUD
        ├── obligations discursives
        ├── références / ellipses
        ├── réparations / clarifications
        └── autres hypothèses pragmatiques
        │
        ▼
Active Graph / Soar / raisonnement
```

Cette chaîne n’est pas nécessairement strictement sérielle. Certains analyseurs, notamment Dynamic Syntax, peuvent travailler directement sur le flux lexical en parallèle d’ERG. En revanche, les étapes de contexte dialogique et de mise à jour doivent pouvoir exploiter explicitement les structures produites en amont.

Une analyse conversationnelle ne remplace jamais les analyses grammaticales ou sémantiques qui la supportent. Elle ajoute de nouvelles structures avec leur provenance.

---

# 35. Stack théorique et statut réel des implémentations

La couche conversationnelle distingue strictement trois choses :

1. **le formalisme théorique** ;
2. **l’outil ou le corpus qui l’implémente ou l’illustre** ;
3. **la représentation cognitive interne**, qui reste propre à cette architecture.

| Niveau | Formalisme | Outil / ressource open source de référence | Statut dans l’architecture |
|---|---|---|---|
| grammaire incrémentale de dialogue | Dynamic Syntax, éventuellement DS-TTR | **DyLan** Java LGPL ; port Python expérimental `dynamicsyntax` | analyseur externe réel à POC |
| phonologie / grapheme-to-phoneme | IPA, traits phonologiques, G2P | **Epitran**, **PanPhon**, éventuellement Phonetisaurus | capteurs externes ; plusieurs candidats possibles |
| transformations de forme | weighted finite-state transducers | **OpenFst**, **Pynini** | formalisme algorithmique explicite pour relations de forme ; aucune sémantique imposée |
| acquisition sémiotique ouverte | relations cross-représentation + induction | graphe commun, retrieval structurel, moteur d’induction | cœur interne à développer ; pas un dictionnaire extensible |
| sémantique/contextualisation du dialogue | **KoS + Type Theory with Records (TTR)** | publications et ressources TTR ; pas de moteur général mature retenu à ce stade | référence formelle ; représentation/adaptateur à développer |
| fonctions communicatives | **DIT++ / ISO 24617-2:2020 / DiAML** | **DialogBank** | standard + corpus annoté ; pas un parseur automatique général |
| relations discursives inter-tours | **SDRT** | **STAC** ; jeux DISRPT selon les tâches | formalisme + corpus ; aucun parseur symbolique général n’est supposé disponible |
| gestion du contexte de dialogue | **Information State Update (ISU)** | **TRINDIKIT / trindikit.py / GoDiS** | implémentations de référence anciennes mais théoriquement explicites |
| grounding | modèles de **Traum**, Grounding Acts / Grounding Units | corpus annotés de grounding, dont ressources LREC-COLING 2024 | théorie + données ; analyseur général à développer/induire |
| attentes normatives du dialogue | **Discourse Obligations** de Traum & Allen | pas de bibliothèque générique maintenue retenue | mécanisme à représenter et tester au-dessus de l’ISU |
| exploration statistique de corpus | aucune théorie cognitive imposée | ConvoKit | utilitaire secondaire uniquement |
| politique de dialogue probabiliste | modèles de dialogue probabilistes | OpenDial | baseline expérimentale uniquement |

Le fait qu’un formalisme ne dispose pas d’un parseur moderne prêt à l’emploi ne justifie pas son remplacement par une feature pratique mais théoriquement faible. Dans ce cas, la qualification correcte est **OUTIL / ADAPTATEUR À DÉVELOPPER**.

---

# 36. Dynamic Syntax et DyLan : grammaire incrémentale de l’interaction

Dynamic Syntax traite l’analyse linguistique comme une construction incrémentale de structure, mot par mot. Cette propriété est particulièrement pertinente pour la conversation, où les productions sont souvent fragmentaires, interrompues, complétées par un autre locuteur ou dépendantes d’un contexte déjà actif.

**DyLan** fournit une implémentation open source de Dynamic Syntax capable de parser et générer incrémentalement, avec des grammaires et lexiques explicites. Le dépôt contient également des mécanismes expérimentaux de grammaire d’inférence d’actes de parole et d’apprentissage de grammaires.

DyLan ne remplace pas ERG.

La POC doit comparer les deux familles d’analyses :

```text
ERG / HPSG / MRS
    excellent niveau phrase
    portée / quantification / structure sémantique riche

Dynamic Syntax / DyLan
    progression mot par mot
    fragments
    extensions
    reprises
    dépendance au contexte conversationnel
```

Les deux analyses doivent pouvoir coexister dans l’Observation Graph :

```text
TurnSpan T42
   ├── ERGAnalysis A17
   │      └── MRS ...
   └── DyLanAnalysis D91
          ├── incremental states ...
          └── final semantic structure ...
```

Aucune conversion forcée de l’une vers l’autre n’est exigée tant qu’une correspondance sans perte n’a pas été démontrée.

Dynamic Syntax peut être exécutée en parallèle du pipeline ERG sur les tours conversationnels. Les couches ultérieures reçoivent ensuite l’ensemble des analyses compatibles.

---

# 37. KoS et TTR : le contexte conversationnel comme objet linguistique formel

**KoS** est une théorie formelle du contexte en dialogue. Elle traite explicitement des phénomènes difficiles à décrire avec une grammaire purement phrastique : fragments, reprises, clarification, réparation, questions actives, changements de locuteur et contexte partagé.

Son support sémantique est **Type Theory with Records (TTR)**, qui permet de représenter de manière structurée des objets tels que :

```text
individus
situations
propositions
questions
types d’événements
records de contexte
contraintes dépendantes
```

KoS introduit notamment le concept de **Dialogue Gameboard (DGB)** pour formaliser le contexte public d’une conversation. Les descriptions KoS peuvent inclure des structures analogues à :

```text
speaker / addressee
facts
moves
pending material
questions under discussion
```

Ces noms ne deviennent **pas** les catégories internes obligatoires du système.

L’architecture conserve plutôt :

```text
ExternalDialogueContextAnalysis
    formalism = KoS/TTR
    source_turns = ...
    record_structure = ...
    dependencies = ...
    unresolved_fields = ...
```

KoS/TTR joue ici le même rôle conceptuel qu’un formalisme sémantique externe : il propose une analyse attribuée et testable du contexte conversationnel.

Aucun moteur KoS/TTR général, maintenu et suffisamment mature pour être adopté comme dépendance fondamentale n’est supposé disponible. L’architecture prévoit donc une **représentation TTR/DGB minimale à développer**, strictement comme adaptateur/formalisme d’analyse, pas comme ontologie cognitive finale.

---

# 38. DIT++, ISO 24617-2 et DiAML : fonctions communicatives formalisées

ISO 24617-2:2020 fournit un cadre standardisé pour annoter les actions communicatives accomplies par des contributions au dialogue. Il est fondé sur des travaux théoriques de dialogue, notamment DIT/DIT++, et autorise des annotations multidimensionnelles : une même unité peut participer simultanément à plusieurs fonctions communicatives.

La norme fournit également **DiAML**, un langage formel de représentation des annotations.

Le **DialogBank** fournit des dialogues annotés selon ISO 24617-2 et constitue donc une ressource de référence pour vérifier les structures attendues.

Le rôle dans l’architecture est :

```text
utterance interpretation bundle
       +
previous dialogue context
       ↓
ISO / DIT++ analysis candidate
       ↓
communicative-function annotations
functional-segment boundaries
dependencies / targets
dimensions
```

Le point critique est que **DialogBank n’est pas un analyseur automatique** et ISO 24617-2 n’est pas un classifieur prêt à l’emploi.

La POC doit donc distinguer :

```text
FORMALISME DISPONIBLE       oui
ANNOTATIONS DE RÉFÉRENCE    oui
LANGAGE DE REPRÉSENTATION   oui
PARSEUR AUTOMATIQUE GÉNÉRAL non supposé
```

Un analyseur automatique éventuel devra être développé ou évalué séparément. Ses sorties resteront des annotations externes concurrentes, jamais des vérités cognitives.

---

# 39. SDRT : structure discursive des conversations multi-tours

RST/eRST reste utile pour la structure rhétorique. Pour la conversation multi-tours, **Segmented Discourse Representation Theory (SDRT)** apporte une théorie plus directement adaptée aux relations discursives complexes, aux dépendances non locales et aux conversations où plusieurs fils s’entrelacent.

Le corpus **STAC** fournit des conversations multi-participants annotées selon une approche SDRT. Il sert de référence pour des structures telles que :

```text
EDU / discourse unit
speaker
attachment target
relation candidate
thread structure
cross-turn dependency
```

L’analyse SDRT se place après ou en interaction avec la sémantique des unités :

```text
MRS / DS semantic candidates
        +
turn / reply structure
        +
prior discourse graph
        ↓
SDRT candidate graph
```

Des parseurs de discours de recherche existent, mais plusieurs implémentations modernes reposent sur des modèles neuronaux ou des stacks anciennes. L’architecture **ne suppose donc pas l’existence d’un parseur SDRT symbolique général et fiable** comparable à ERG.

Dans un premier temps, STAC et les annotations SDRT servent à :

- valider notre schéma de représentation ;
- mesurer les informations que le formalisme apporte réellement ;
- alimenter l’induction offline ;
- construire des cas de test gold ;
- guider un éventuel analyseur propre à développer.

---

# 40. Information State Update : rendre les effets d’un tour exécutables

L’approche **Information State Update (ISU)** fournit le pont entre analyse linguistique et dynamique conversationnelle.

Un tour n’est pas seulement classé. Il produit des **candidats de transformation d’un état informationnel explicite**.

Conceptuellement :

```text
DialogueState_n
      +
interpreted utterance
      +
communicative / discourse analyses
      ↓
update rules / constraints
      ↓
DialogueState_n+1 candidate(s)
```

**TRINDIKIT**, `trindikit.py` et **GoDiS** sont des implémentations historiques importantes de cette approche. Elles montrent concrètement comment :

- un information state peut être inspecté ;
- des règles de mise à jour possèdent préconditions et effets ;
- des questions ouvertes peuvent être manipulées ;
- des contributions peuvent être intégrées ou accommodées ;
- la sélection d’un prochain mouvement peut être séparée de l’interprétation.

Ces outils sont anciens et ne doivent pas devenir une dépendance de production obligatoire. Leur intérêt est comparable à une **implémentation de référence d’une théorie**.

Dans notre architecture, l’ISU est projeté vers le graphe commun :

```text
ExternalISUTransitionCandidate
    before_state_ref = ...
    triggering_analyses = ...
    conditions = ...
    bindings = ...
    proposed_additions = ...
    proposed_retractions = ...
    unresolved_issues = ...
```

Soar et le Learned Graph restent responsables de la cognition active et de l’apprentissage. L’ISU fournit une structure dialogique interprétable supplémentaire.

---

# 41. Grounding, QUD et obligations discursives

Trois familles de phénomènes doivent être représentées explicitement parce qu’elles décrivent des propriétés réelles de l’interaction et disposent de traditions théoriques établies.

## 41.1 Grounding

Les travaux de Clark, Traum et leurs successeurs modélisent comment les participants accumulent des preuves qu’un contenu a été perçu, compris, accepté pour les besoins de l’échange, corrigé ou laissé incertain.

Les **Grounding Acts** et **Grounding Units** de Traum fournissent une base formelle et ont encore servi récemment à annoter des corpus de dialogue.

Le système ne stocke jamais simplement :

```text
shared = true
```

Il conserve l’histoire :

```text
content C introduced at T1
acknowledgement at T2
clarification request at T3
repair at T4
new evidence at T5
```

## 41.2 Questions Under Discussion

Les approches KoS et issue-based dialogue management représentent les questions actuellement actives et la manière dont des fragments ultérieurs peuvent les résoudre.

Ainsi :

```text
A: Où habite Alice ?
B: Montréal.
```

peut être analysé comme :

```text
QUD candidate q = where(Alice)
fragment semantics = Montreal
resolution candidate = q ↦ Montreal
```

sans modifier l’observation brute `Montréal.`.

## 41.3 Discourse Obligations

Traum & Allen montrent qu’une interaction peut créer des **obligations discursives** distinctes des croyances, buts et intentions classiques.

Une question, par exemple, peut modifier le contexte de telle manière qu’une réponse devient conventionnellement attendue.

L’architecture représente ces obligations comme des structures candidates attribuées :

```text
obligation_candidate O
    created_by = turn / analysis
    bearer = participant
    content_constraint = ...
    support = ...
    satisfied_by = ... | unresolved
```

Elles ne constituent pas une enum universelle de comportements. L’induction peut apprendre quand ces analyses sont prédictives et comment elles interagissent avec les autres structures.

---

# 42. Coréférence inter-tours, ellipses, réparations et inférences pragmatiques

Les phénomènes conversationnels difficiles doivent utiliser **les résultats des analyses précédentes**, pas repartir du texte brut.

Exemple :

```text
A : Jean a acheté une voiture.
B : Rouge ?
A : Oui.
```

L’analyse de `Rouge ?` peut combiner :

```text
Dynamic Syntax
    fragment / incremental continuation candidate

ERG / lexical semantics
    adjective/color predicate candidate

KoS / QUD
    active issue linked to car properties

SDRT
    attachment to prior contribution

salience / reference candidates
    vehicle introduced in previous turn
```

et construire une hypothèse :

```text
color(car_1, red)
```

avec tous ses supports, plutôt que de créer directement un fait interne.

Le même principe vaut pour :

- la coréférence inter-tours ;
- les fragments non phrastiques ;
- les reprises et complétions collaboratives ;
- les auto-réparations et réparations par l’interlocuteur ;
- les demandes de clarification ;
- les présuppositions ;
- les implicatures ;
- les retours à un sujet antérieur.

KoS est particulièrement pertinent pour les non-sentential utterances, la clarification et la réparation. Dynamic Syntax fournit des structures incrémentales. ERG/MRS fournit la sémantique propositionnelle et les contraintes de portée. Le graphe de provenance conserve l’origine de chaque hypothèse.

Les implicatures et présuppositions générales ne disposent pas ici d’un analyseur open source symbolique suffisamment général pour être adopté comme vérité technique. Elles restent donc des **hypothèses à produire par contraintes et induction**, avec support explicite.

---

# 43. Outils utilitaires, corpus et invariant de la couche conversationnelle

Certains outils restent utiles, mais leur rôle est désormais précisément limité.

## 43.1 ConvoKit

ConvoKit reste intéressant pour :

```text
charger des corpus conversationnels
naviguer dans les speakers / turns / reply links
calculer des statistiques
explorer des séquences
faire des analyses de coordination ou de style
construire rapidement des jeux de données de POC
```

Il **n’est pas** un analyseur conversationnel fondamental et ne définit aucune représentation cognitive.

## 43.2 OpenDial

OpenDial peut servir de baseline pour :

```text
politiques probabilistes
états de dialogue explicites
gestion d’incertitude
comparaison comportementale
```

Il ne remplace ni KoS/TTR, ni l’ISU, ni Soar.

## 43.3 Corpus et annotations de référence

Les ressources suivantes servent principalement de données gold ou semi-gold :

```text
DialogBank          ISO 24617-2 / DiAML
STAC                SDRT
Switchboard         dialogue acts / conversations humaines
Grounding corpora   Grounding Acts / Grounding Units
DISRPT              segmentation / relations de discours selon plusieurs formalismes
```

Elles sont cruciales pour les POC même lorsqu’aucun parseur automatique satisfaisant n’existe.

## 43.4 Baselines auxiliaires

CoreNLP, Coreferee, TextTiling et autres outils peuvent rester utilisés comme **capteurs spécialisés ou baselines** pour la coréférence, la segmentation thématique ou des phénomènes particuliers. Ils ne sont pas promus au rang de théorie générale de la conversation.

## 43.5 Invariant architectural

À tout moment, il doit être possible de distinguer :

```text
OBSERVATION BRUTE
        ↓
ANALYSE GRAMMATICALE / SÉMANTIQUE EXTERNE
        ↓
ANALYSE CONVERSATIONNELLE FORMELLE EXTERNE
        ↓
CANDIDAT DE MISE À JOUR D’ÉTAT
        ↓
STRUCTURE ACTIVE INTERNE
        ↓
STRUCTURE APPRISE
```

Une annotation ISO n’est pas une intention réelle par décret.

Un graphe SDRT n’est pas la vérité discursive par décret.

Un état KoS ou ISU n’est pas l’ontologie cognitive du système par décret.

Ces formalismes jouent le même rôle méthodologique qu’ERG/MRS : ils fournissent des **structures théoriquement motivées, inspectables et falsifiables** sur lesquelles le système peut apprendre.

---

# 44. Stack Overflow comme corpus

La source fournit naturellement des structures comme :

```text

posts

parent links

authors

scores

accepted answers

comments

code blocks

timestamps

tags

```

Ces propriétés sont conservées telles quelles.

À travers des millions de threads, le moteur peut ensuite découvrir que certaines configurations structurelles sont suivies de certaines transformations, et que certaines transformations sont associées à certains résultats.

Ces régularités deviennent des patterns appris.

---

# 45. Reddit comme corpus

Reddit fournit une autre topologie :

```text

reply tree

authors

timestamps

scores

nested exchanges

quotations

edits when available

```

Le moteur n’a pas besoin qu’on lui explique quelles sortes d’interactions humaines il devrait trouver.

Il détecte les régularités à partir des structures observées.

---

# 46. Wikipédia comme corpus

Wikipédia fournit :

```text

structured exposition

sections

cross-references

citations

chronology

definitions

descriptions

```

Ces propriétés donnent un autre type d’expérience.

Les abstractions découvertes sur plusieurs corpus peuvent être comparées et fusionnées lorsqu’elles partagent une structure suffisamment générale.

---

# 47. Contexte actif online

Lorsqu’un utilisateur envoie un message, l’analyse produit un nouveau fragment de graphe.

Le contexte actif contient alors :

```text

active graph fragments

active variables

active constraints

active hypotheses

active bounded interpretation beam

active structural-diversity reserves / outlier candidates

active justification and contradiction fragments

active retrieved patterns

active source context

active interaction history

active interaction-state structures

active KoS/TTR or ISU-derived context hypotheses

active QUD / pending issues / discourse obligations

active grounding histories and candidates

active expected continuations learned from prior episodes

active unresolved references / bindings

active topic and entity-salience hypotheses

```

Il n’est pas une liste d’états conversationnels prédéfinis. Les structures interactionnelles actives sont soit observables, soit proposées par des formalismes externes (DS, ISO/DIT++, SDRT, KoS/TTR, ISU, grounding), soit apprises par induction. Le runtime peut leur attribuer des identifiants et un statut opérationnel sans transformer des catégories humaines comme « question », « réponse » ou « refus » en primitives cognitives obligatoires.

Le contexte actif n’est pas non plus le dépôt complet de l’incertitude. Le gestionnaire externe conserve les alternatives factorisées ; le runtime reçoit seulement les quelques assemblages nécessaires au cycle courant. Une famille d’hypothèses faiblement classée mais structurellement distincte peut être conservée comme réserve de diversité afin d’éviter une convergence prématurée.

---

# 48. Récupération mémoire online

À partir du contexte actif, le système peut récupérer :

```text

structurally similar episodes

related abstractions

relevant learned transformations

compatible constraints

contradictory structures

prior continuations with known outcomes

prior supports / contradictions for active hypotheses

prior selection events and their downstream outcomes

compatible / conflicting assumption sets when materialization is required

```

La récupération est structurelle, pas seulement lexicale.

Lorsque l’entrée réactive une hypothèse persistante, la récupération doit privilégier son prototype partagé et son Evidence Ledger plutôt que recopier toutes les occurrences qui l’ont déjà soutenue. Les épisodes détaillés ne sont chargés que si le raisonnement ou l’audit les exige.

---

# 49. Raisonnement online

Le moteur combine :

```text

current graph

constraints

retrieved knowledge

learned transformations

procedural chunks

active goals

```

pour construire plusieurs évolutions possibles.

Plusieurs hypothèses peuvent rester actives simultanément.

Le raisonnement ne doit cependant pas explorer automatiquement le produit cartésien de ces hypothèses. Il demande des compositions globales à la demande, vérifie localement leurs contraintes, partage les sous-structures communes et abandonne les assemblages inutiles après le cycle sans supprimer leurs composants persistants.

## 49.1 Persistent Situation / World State Projection

Le moteur doit être capable de construire des **entités particulières persistantes**, de leur associer des propriétés/relations, d’appliquer des transformations successives et d’interroger l’état symbolique résultant.

Le schéma général est :

```text
Observation linguistique
        ↓
structures candidates
        ↓
bindings d'entités particulières
        ↓
CURRENT SITUATION / WORLD GRAPH
        ↓
Transformation_1
        ↓
Transformation_2
        ↓
Transformation_3
        ↓
NEW GRAPH STATE
        ↓
query / reasoning over resulting state
```

La création d’une entité comme `Julie_17`, de sa chambre comme `Room_42`, d’une propriété de clarté, d’un livre particulier ou d’une lampe particulière ne doit pas provenir d’une liste de concepts attendus. Elle résulte des bindings, des structures linguistiques, des hypothèses actives et des transformations apprises.

## 49.2 Exemple : propriété qualitative

```text
Jack est lent comme une tortue.
```

Le système doit pouvoir aboutir à une structure qualitative comme :

```text
Entity Jack_17
PropertyInstance P81
    bearer = Jack_17
    dimension = speed-like learned/formal structure
    value = LOW-like relational/qualitative structure
```

avec des supports tels qu’une structure de comparaison et des connaissances récupérées sur la tortue. Aucune valeur numérique ne doit être inventée si les données n’en fournissent pas.

## 49.3 Exemple : identité, référence et inversion

```text
Il fait clair dans la chambre de Robert.
C'est l'inverse dans la chambre de Julia.
```

Le système doit construire au minimum des bindings distincts pour Robert, Julia et leurs chambres, conserver la propriété active du premier énoncé, résoudre la référence portée par `C'`, interpréter la structure associée à `inverse`, puis appliquer cette transformation à la chambre de Julia.

Conceptuellement :

```text
Robert_1 -> Room_24
Julia_1  -> Room_51

BrightnessState_1
    bearer = Room_24
    qualitative_value = HIGH-like structure

reference(previous property/state)
        +
inverse-like transformation
        +
Room_51 binding
        ↓
BrightnessState_2
    bearer = Room_51
    qualitative_value = LOW-like structure
```

Les labels humains `brightness`, `HIGH`, `LOW` et `inverse` servent ici à inspecter le POC ; ils ne constituent pas nécessairement les primitives cognitives finales.

## 49.4 Transformations successives et état final

Le moteur doit gérer des séquences telles que :

```text
Marie pose le livre sur la table.
Jean prend le livre.
Il le donne à Luc.
```

avec un état final compatible avec :

```text
possessor(book_instance) = Luc_instance
location(book_instance) != table_instance
```

ou :

```text
Julie entre dans sa chambre.
Elle allume la lampe.
Puis elle l'éteint.
```

avec l’état final de la lampe distinct des états intermédiaires et conservant l’ordre des transformations.

Ce mécanisme est la jonction directe entre sémantique, coréférence, mémoire épisodique, temporalité relationnelle, contraintes, induction et raisonnement.

---

# 50. Construction des transformations candidates

L’espace d’action n’est pas une enum conversationnelle.

Le système produit des transformations candidates du graphe courant :

```text

CurrentGraph

      +

RetrievedPatterns

      +

Constraints

      ↓

CandidateTransformation_1

CandidateTransformation_2

CandidateTransformation_3

...

```

Les transformations candidates sont générées à partir du **beam d’interprétations actif**, pas depuis toutes les combinaisons possibles conservées sur disque. Une même transformation peut référencer des sous-structures partagées entre plusieurs interprétations sans les recopier.

Une transformation est décrite en termes de primitives générales de graphe.

Elle peut introduire, relier, modifier, demander un binding manquant, instancier un pattern appris, rendre explicite une structure récupérée, ou produire toute autre transformation composable autorisée par les mécanismes de base.

---

# 51. Sélection des transformations

Les candidates sont évaluées selon des critères généraux :

```text

goal compatibility

constraint satisfaction

predicted utility

structural fit

past outcome statistics

information gain

cost

uncertainty reduction

novelty

consistency

```

La sélection ne dépend pas d’une catégorie conversationnelle écrite à la main.

Il faut distinguer deux sélections :

```text
INTERPRETATION RANKING
    -> quelles hypothèses / compositions entrent dans le beam actif

ACTION / TRANSFORMATION SELECTION
    -> quelle évolution du graphe ou réponse est exécutée
```

Le premier ranking est calculé à partir du Evidence Ledger et du contexte courant ; le second évalue les transformations possibles. Aucun des deux n’efface les alternatives persistantes.

---

# 52. Planification communicative : frontière entre décision et langage

La transformation cognitive sélectionnée ne doit pas être envoyée directement au réalisateur linguistique.

Une couche intermédiaire construit un objet inspectable décrivant **ce qui doit être communiqué et sous quelles contraintes**, avant de choisir les mots.

```text

selected transformation

        ↓

communicative target / interaction-state delta

        ↓

content selection

        ↓

discourse organization

        ↓

reference / detail / style constraints

        ↓

linguistic realization

```

Cette couche ne réintroduit pas une enum d’intentions. Le but communicatif peut être une structure apprise ou une transformation anonyme dont l’effet attendu est connu par expérience.

Des noms comme `answer`, `clarify`, `acknowledge` ou `correct` peuvent être utilisés dans les traces de debug lorsqu’un mapping humain existe, mais ne sont pas nécessaires au fonctionnement interne.

---

# 53. But communicatif et sélection du contenu

Le système doit distinguer :

```text

ce qu’il sait / récupère

ce qu’il choisit de modifier dans l’interaction

ce qu’il choisit effectivement d’exprimer

```

Soar, les contraintes actives, les attentes interactionnelles et les statistiques d’outcomes peuvent produire plusieurs cibles candidates. Après sélection, le planificateur choisit un sous-graphe communicable minimalement suffisant.

Chaque élément sélectionné doit conserver :

```text

source graph reference

reason for inclusion

relation to active constraint / goal

novelty relative to interaction history

redundancy

uncertainty

provenance

```

Le système doit pouvoir omettre une information pourtant vraie et activée lorsqu’elle est inutile au but actuel. À l’inverse, il doit pouvoir inclure une justification ou une précision lorsqu’un pattern appris montre qu’elle améliore l’outcome attendu.

Les traces de sélection de GoDiS/TRINDIKIT et, secondairement, OpenDial peuvent servir de baselines expérimentales. Soar reste le moteur principal de décision ; le Learned Graph et les épisodes fournissent les régularités permettant de ne pas coder manuellement une politique conversationnelle.

---

# 54. Organisation discursive et stratégie référentielle de la réponse

Lorsque plusieurs structures doivent être communiquées, leur ordre et leurs relations doivent être décidés avant SimpleNLG.

Le plan peut contenir :

```text

selected propositions / graph fragments

ordering constraints

candidate discourse relations

sentence grouping constraints

reference targets

salience estimates

ambiguity constraints

morphosyntactic requirements

```

RST/eRST et SDRT servent ici de sources d’observations permettant d’apprendre comment des contenus sont organisés dans les corpus et les dialogues. Il ne devient pas un planificateur discursif obligatoire.

Pour chaque mention prévue, le système doit pouvoir choisir entre une description plus complète, une répétition, un pronom, un démonstratif ou une ellipse en fonction des structures de saillance et des risques d’ambiguïté appris.

CoreNLP/Coreferee peuvent servir de baselines d’analyse des réalisations observées ; ERG et SimpleNLG fournissent des contraintes grammaticales ; la stratégie référentielle elle-même appartient au planificateur communicatif.

---

# 55. Quantité, pertinence, initiative et continuation

La réponse ne doit pas être définie uniquement par le fait qu’une information est récupérable.

Le planificateur doit pouvoir apprendre des régularités reliant :

```text

interaction state

user / source context

amount of expressed content

presence or absence of a follow-up move

topic continuation or closure

observable outcome

```

Il peut ainsi produire un budget de contenu et une décision d’initiative sans règle universelle du type « toujours poser une question à la fin ».

DialogBank, STAC, Switchboard et les corpus de grounding fournissent les observations principales pour ces régularités. ConvoKit peut faciliter leur exploration statistique, sans fournir la théorie d’interprétation. Le moteur d’induction doit apprendre quand une continuation supplémentaire est utile, quand un tour minimal suffit et quand une nouvelle demande d’information est justifiée.

La quantité, la pertinence et l’initiative deviennent donc des conséquences de patterns appris et de contraintes actives, pas des réglages fixes du chatbot.

---

# 56. Réalisation linguistique

Une fois le plan communicatif construit, la couche de réalisation transforme ses structures en langage.

```text

communicative plan

    ↓

ordered content + reference constraints

    ↓

syntactic / morphological realization

    ↓

surface variation

    ↓

text

```

SimpleNLG peut servir de premier réalisateur déterministe. ERG et les autres ressources linguistiques peuvent être utilisés pour vérifier ou enrichir les contraintes de forme.

La génération ne doit ni choisir le but conversationnel, ni inventer le contenu, ni résoudre une ambiguïté cognitive. Elle réalise un plan déjà sélectionné et traçable.

---

# 57. Apprentissage de la réalisation

La couche de surface peut commencer de façon relativement déterministe.

Mais elle peut elle aussi apprendre progressivement des structures de réalisation à partir du corpus.

Ainsi, la fluidité linguistique peut devenir une autre couche d’induction plutôt qu’une collection de templates écrits à la main.

Le système doit notamment pouvoir observer plusieurs réalisations d’un même type de plan communicatif et apprendre leurs différences de registre, longueur, structure référentielle et ordre de surface, sans confondre ces variations avec une différence de contenu cognitif.

---

# 58. Chunking Soar

Soar peut compiler des chaînes de raisonnement fréquemment utilisées.

Exemple abstrait :

```text

StatePattern_1

    ↓

multi-step reasoning

    ↓

Transformation_7

```

peut devenir :

```text

StatePattern_1

    ↓

Transformation_7

```

Le chunk compile une procédure observée ; il ne dépend pas d’une taxonomie conversationnelle prédéfinie.

---

# 59. Mémoire procédurale

Les procédures réutilisables doivent provenir de :

```text

experience

reasoning

chunking

induction

compression

```

et non d’un manuel de comportements écrit par les développeurs.

---

# 60. Provenance

Toute structure doit pouvoir remonter vers :

```text

origin

source document

source author

source timestamp

source position

analysis method

inference chain

supporting episodes

contradicting episodes

```

Une abstraction n’efface donc jamais son histoire.

---

# 61. Support épistémique

Plutôt qu’une taxonomie rigide de « vérité », chaque proposition ou structure peut porter des propriétés générales :

```text

direct source support

derived support

counterevidence

uncertainty

source disagreement

temporal validity

```

La consolidation de connaissances s’appuie sur ces signaux.

---

# 62. Architecture de stockage

```text

RAW STORE

  contenu original

SOURCE STORE

  structure native et provenance

EPISODIC STORE

  expériences structurées

PATTERN STORE

  structures induites

STATISTICS STORE

  compteurs et distributions

INDEX STORE

  retrieval rapide

SOAR RUNTIME

  contexte actif

```

Le stockage massif ne dépend pas de Soar.

---

# 63. Recherche structurelle

Le retrieval doit pouvoir effectuer des requêtes de sous-graphes.

Exemple conceptuel :

```text

Find episodes where:

graph shape G1

is followed by transformation T

then by a graph satisfying constraint C

```

Cela exige des indexes adaptés aux structures, pas seulement un moteur full-text.

Le retrieval doit également pouvoir changer de plan de représentation. Une requête issue d’une forme écrite peut, sans la remplacer, chercher :

```text
phonological neighbours
graphemic transformations
known abbreviations / segmentations
lexical-semantic structures reached through those candidates
conversation episodes with similar downstream effects
```

Chaque chemin de récupération conserve le type de relation qui l’a produit. Un résultat obtenu par proximité phonologique ne devient donc pas un synonyme par simple transitivité.

---

# 64. Relation entre OFFLINE et ONLINE

```text

OFFLINE INGESTION

      ↓

GLOBAL MEMORY

      ↓

ONLINE INTERACTION

      ↓

NEW EPISODES

      ↓

OFFLINE INGESTION

```

Le système continue donc à apprendre de ses propres interactions.

Les interactions du système gardent leur provenance distincte afin de ne pas confondre ce qu’il a lui-même produit avec les données extérieures.

---

# 65. Contrôle anti-hardcoding

Chaque ajout manuel doit passer le test suivant :

> Est-ce une primitive mécanique indispensable ou une abstraction que le système devrait apprendre ?

Si l’ajout décrit une abstraction du monde, du raisonnement ou du discours, il est suspect.

La première réponse doit être d’améliorer :

```text

representation

induction

retrieval

compression

candidate generation

selection

```

avant d’ajouter un cas particulier.

---

# 66. Validation conversationnelle transversale

Le chatbot doit être évalué sur des séquences multi-tours, pas seulement sur la grammaticalité de phrases isolées.

Les scénarios minimaux comprennent :

1. une structure interrogative dont la réponse résout effectivement une variable ouverte ;
2. une réponse elliptique telle que `Montréal.` reliée au bon contexte antérieur ;
3. une ambiguïté de référence maintenue jusqu’à clarification plutôt que résolue arbitrairement ;
4. une correction où l’ancien contenu reste traçable et le nouvel état interactionnel est mis à jour ;
5. une digression suivie d’un retour à un sujet plus ancien ;
6. une réponse indirecte dont l’implicature reste distincte du contenu littéral ;
7. un plan communicatif entièrement inspectable avant réalisation ;
8. plusieurs réalisations différentes d’un même plan sans modification du contenu ou des engagements sous-jacents ;
9. un fragment dont l’analyse dépend réellement d’un QUD ou d’un Dialogue Gameboard antérieur ;
10. un cas où ERG et Dynamic Syntax apportent des structures complémentaires plutôt que dupliquer la même information ;
11. une mise à jour ISU dont les préconditions, effets et supports linguistiques sont entièrement traçables ;
12. une forme inconnue telle que `io` conservée intacte tout en produisant plusieurs hypothèses graphiques, phonologiques et contextuelles simultanées ;
13. un cas où une proximité phonologique mène à un bon candidat sans provoquer une fusion sémantique erronée ;
14. un cas où `io` récupère à la fois `yo` et `I/O`, puis où le contexte conserve ou renforce les deux chemins au lieu de sélectionner arbitrairement un seul « sens » ;
15. une série d’exceptions à un pattern qui finit par produire une spécialisation ou un nouveau pattern plutôt que d’être supprimée comme bruit ;
16. une innovation lexicale ou graphique rencontrée dans plusieurs épisodes qui devient une structure apprise traçable sans modification rétroactive des observations originales.
17. une première occurrence de `io` où une mauvaise hypothèse est sélectionnée, suivie d’épisodes qui renforcent une autre hypothèse, puis une occurrence ultérieure correctement interprétée sans réécriture du premier épisode ;
18. un cas combinant plusieurs ambiguïtés locales où le système prouve qu’il n’a pas matérialisé leur produit cartésien complet ;
19. un cas où le candidat au meilleur score appartient à une famille déjà représentée dans le beam mais où une hypothèse plus faible et structurellement distincte survit grâce à la réserve de diversité ;
20. un test de montée en charge montrant que mille occurrences soutenant la même hypothèse créent principalement des références/agrégats supplémentaires plutôt que mille copies du même sous-graphe ;
21. un test de stockage froid où une hypothèse archivée peut être reconstruite depuis ses observations et justifications lorsque du nouveau contexte la rend pertinente.

Les erreurs importantes à mesurer sont notamment :

```text

wrong referent

forgotten unresolved structure

forced ambiguity resolution

lost topic

unrepaired contradiction

irrelevant continuation

unnecessary repetition

surface generator inventing content

interaction state inconsistent with episode history

destructive normalization of unknown form

premature collapse of phonological / graphical / semantic hypotheses

unknown-form analysis failure causing cognitive data loss

cross-representation link treated as semantic identity

Cartesian explosion of local ambiguities

retroactive rewriting of an earlier selected interpretation

active beam containing near-duplicate candidates only

hypothesis pruning destroying reconstruction evidence

full episode duplication inside every hypothesis

```

Le benchmark principal peut mesurer le nombre de tours avant rupture de cohérence, mais chaque rupture doit également être explicable par les traces du graphe, des analyses externes, de Soar, de la sélection et du plan communicatif.

## 66.1 CORE-01 — Composition sémantique, identité et projection d’état

CORE-01 vérifie qu’une suite d’énoncés peut créer des entités particulières, maintenir leur identité, appliquer plusieurs transformations et permettre d’interroger correctement l’état final.

### CORE-01A — Moteur symbolique isolé

Le NLP est court-circuité. Des structures symboliques contrôlées sont injectées directement afin de tester :

```text
bindings
identity persistence
state transitions
temporal/causal ordering
constraints
contradictions
property updates
relation updates
query of final state
```

Exemple :

```text
ENTITY Julia_1
ENTITY Room_1
associated_with(Julia_1, Room_1)
STATE brightness(Room_1) = LOW-like structure
TRANSFORM increase_brightness(Room_1)
```

Question centrale :

> Si les analyseurs fournissent exactement les structures nécessaires, le moteur sait-il maintenir correctement un monde symbolique et ses transformations ?

CORE-01A doit être réalisé relativement tôt, après stabilisation minimale de GRAPH / bindings / contraintes, sans attendre la fin de toutes les POC analytiques.

### CORE-01B — Intégration bout en bout

Le même test est ensuite exécuté depuis le langage naturel réel :

```text
texte naturel
    ↓
analyses formelles
    ↓
coréférence / discours / dialogue
    ↓
hypothèses factorisées
    ↓
bindings d'entités particulières
    ↓
transformations
    ↓
état du graphe
    ↓
requête
    ↓
réponse
```

Fixtures minimales :

```text
Jack est lent comme une tortue.
→ query on Jack's speed-like state

La chambre de Robert est claire.
C'est l'inverse dans celle de Julia.
→ query on Julia-room clarity-like state

Marie pose le livre sur la table.
Jean prend le livre.
Il le donne à Luc.
→ final possessor/location state

Paul est plus grand que Marc.
Marc est plus grand que Jules.
→ derived comparative relation

Julie entre dans sa chambre.
Elle allume la lampe.
Puis elle l'éteint.
→ final lamp state distinct from intermediate state
```

CORE-01B valide simultanément création d’entités particulières, référence, composition sémantique, continuité d’identité, transformations, temporalité relationnelle, contraintes, provenance et interrogation du graphe final.

## 66.2 Validation temporelle minimale

Avant de considérer la couche temporelle comme opérationnelle, tester au minimum :

```text
observable ordering
temporal discourse relations
temporal anaphora
reference-time structure
tense/aspect candidates
event/state relations
episode sequences
temporal context retrieval
temporal ambiguity and revision
state persistence
induction of recurrent temporal patterns
relational answer to "when did I hear this?"
optional mapping to external calendar/clock anchors without collapse
```

Les POC HeidelTime/Duckling sont des POC d’analyseurs de surface externes, pas des POC du cœur temporel.

---

# 67. Test de générativité

Le système est probablement sur la mauvaise voie si nous pouvons écrire une enum exhaustive de ce qu’il sait faire.

Le système est sur la bonne voie si :

```text

ses primitives mécaniques sont finies

mais

ses structures apprises sont ouvertes

et

ses abstractions peuvent se composer récursivement

```

---

# 68. Références théoriques, implémentations de dialogue et programme temporel

Références principales retenues pour les POC :

- **Dynamic Syntax / DyLan** — parser/générateur incrémental open source : `https://github.com/Dynamics-of-Language/DyLan`
- **Port Python expérimental de DyLan** : `https://github.com/incrementaliser/DynamicSyntax`
- **ISO 24617-2:2020** — actes de dialogue / DiAML : `https://www.iso.org/standard/76443.html`
- **DialogBank** — corpus annoté ISO 24617-2 : `https://dialogbank.lsv.uni-saarland.de/`
- **STAC** — corpus de dialogues annoté dans le style SDRT : `https://aclanthology.org/L16-1432/`
- **Information State / TRINDI** — Larsson & Traum : `https://doi.org/10.1017/S1351324900002539`
- **Discourse Obligations** — Traum & Allen : `https://aclanthology.org/P94-1001/`
- **Grounding Acts / Grounding Units** — ressource récente : `https://aclanthology.org/2024.lrec-main.352/`
- **KoS / dialogue grammar** — Jonathan Ginzburg, *The Interactive Stance* ; TTR comme formalisme de support.
- **Epitran** — transcription orthographie → IPA et alignements de segments : `https://github.com/dmort27/epitran`
- **PanPhon** — représentation des segments par traits phonologiques : `https://github.com/dmort27/panphon`
- **OpenFst** — bibliothèque de weighted finite-state transducers : `https://github.com/google-research/openfst`
- **Pynini** — compilation de grammaires de réécriture en WFST : `https://github.com/kylebgorman/pynini`
- **Phonetisaurus** — G2P entraînable sur OpenFst, à utiliser comme baseline lorsque pertinent : `https://github.com/AdolfVonKleist/Phonetisaurus`
- **DS-TTR et apprentissage lexical/dialogique** — travaux d’Eshghi, Yu, Lemon et collaborateurs sur induction et acquisition de significations en dialogue.
- **Assumption-Based Truth Maintenance System (ATMS)** — Johan de Kleer, *An assumption-based TMS*, Artificial Intelligence 28(2), 1986, DOI `10.1016/0004-3702(86)90080-9`. L’architecture en reprend les idées de justifications, dépendances d’hypothèses, contextes incompatibles et partage des résultats, mais refuse l’énumération exhaustive des environnements lorsque celle-ci ferait exploser la combinatoire.
- **Z3** — utilisé comme solveur local de contraintes pour tester la compatibilité d’assemblages d’hypothèses matérialisés à la demande ; il ne constitue pas le gestionnaire persistant des hypothèses.

Ces références documentent les formalismes et leurs ressources. Elles ne transforment aucun label externe en primitive cognitive interne.

Pour la temporalité, les familles suivantes constituent **un programme de recherche à évaluer**, pas une pile déjà adoptée comme ontologie interne : DRT / Temporal DRT, SDRT, Reichenbach, tense/aspect/event semantics, temporal anaphora, modèles psychologiques de contexte temporel et segmentation événementielle, travaux neuroscientifiques sur hippocampe/time cells/séquences/contexte/replay, et formalismes computationnels de graphes relationnels, contraintes, persistance d’état, ordre partiel et incertitude temporelle. Chaque mécanisme doit passer la grille de la section 17.10 avant adoption.

---

# 69. Roadmap

## Phase 1 — Source Layer

Construire les décodeurs et parseurs propres à chaque source.

## Phase 2 — Observation Graph et Transmission / Provenance Graph

Conserver intégralement l’expérience observable, les structures natives des sources ainsi que le contexte d’origine et de transmission de l’information.

## Phase 3 — Deep NLP + Open Semiotic Acquisition

Brancher progressivement les analyseurs symboliques externes, puis valider la coexistence de plusieurs plans d’analyse : ERG/MRS et ressources lexicales, Dynamic Syntax lorsque pertinent, phonologie/G2P avec Epitran/PanPhon, transformations formelles avec OpenFst/Pynini, et retrieval cross-représentation. Vérifier explicitement qu’une forme inconnue reste conservée et peut accumuler plusieurs hypothèses sans normalisation destructive.

## Phase 3A — Temporal Foundation Research

Avant d’implémenter un cœur temporel, étudier formellement linguistique du temps, mémoire épisodique/contextuelle en psychologie, contraintes neuroscientifiques pertinentes et formalismes computationnels. Reclasser HeidelTime/Duckling en analyseurs externes seulement. Fixer les contrats de données du Temporal / Episodic Relation Subsystem et vérifier les invariants de temporalité relationnelle et de non-collapse.

## Phase 4 — Factorized Hypothesis Manager

Implémenter les objets Hypothesis / Justification / Contradiction / SelectionEvent / EvidenceLedger, le partage structurel, la déduplication, la composition paresseuse, la vérification locale de contraintes, le beam actif borné avec diversité, puis le stockage chaud/froid réversible. Valider avec des ambiguïtés synthétiques que le coût suit principalement le nombre d’hypothèses locales et de relations réellement matérialisées plutôt que leur produit cartésien théorique.

## Phase 4A — CORE-01A — State Engine isolé

Dès que représentation commune, bindings et contraintes sont suffisamment stables, injecter des structures symboliques contrôlées et valider identité persistante, transformations successives, ordre, contradictions et interrogation de l’état final. Ce POC doit précéder le développement sérieux du moteur complet.

## Phase 5 — Episodic Store

Conserver les expériences complètes, y compris les hypothèses considérées, les sélections effectuées à l’époque et les outcomes ultérieurs liés sans réécriture rétroactive.

## Phase 6 — Massive Storage + Indexing

Permettre l’ingestion de corpus très grands, avec index séparés pour observations, prototypes d’hypothèses, justifications, statistiques et archives froides.

## Phase 7 — Induction Engine

Détecter les sous-graphes et transformations récurrentes, puis consolider les liens hypothétiques récurrents en prototypes partagés.

## Phase 8 — Compression / Merge / Split

Permettre aux abstractions et familles d’hypothèses de se restructurer sans réécrire les épisodes historiques.

## Phase 9 — Soar Runtime

Brancher working memory, goals, retrieval et chunking ; exposer à Soar uniquement le beam actif et les fragments de justification nécessaires au cycle courant.

## Phase 10 — Discourse Induction

Appliquer l’induction aux structures discursives sans taxonomie cognitive prédéfinie.

## Phase 11 — Formal Dialogue Analysis

Valider Dynamic Syntax/DyLan en parallèle d’ERG, définir l’encapsulation KoS/TTR, importer DialogBank/ISO 24617-2 et STAC/SDRT, puis représenter toutes ces sorties comme analyses externes attribuées. ConvoKit reste un utilitaire de corpus seulement.

## Phase 12 — Information-State / Grounding Runtime

Implémenter et valider les candidats de mise à jour inspirés de l’Information State Update, des QUD, du grounding et des discourse obligations. Utiliser TRINDIKIT/trindikit.py/GoDiS comme références exécutables et apprendre progressivement les régularités multi-tours sans enum conversationnelle interne.

## Phase 13 — Candidate Transformation Engine

Générer des continuations symboliques possibles depuis le beam actif, avec composition d’interprétations uniquement à la demande.

## Phase 14 — Selection Engine

Évaluer séparément le ranking contextuel des interprétations et la sélection des transformations, tout en conservant les alternatives persistantes.

## Phase 15 — Communicative Planning

Construire un plan inspectable de contenu, ordre discursif, stratégie référentielle, quantité et initiative avant toute génération de surface.

## Phase 16 — Surface Realization

Transformer la structure sélectionnée en langage.

## Phase 17 — Continuous Learning

Réinjecter les interactions comme nouveaux épisodes avec provenance séparée ; utiliser corrections et outcomes pour réviser les Evidence Ledgers, les stratégies de ranking et les structures induites sans falsifier les décisions historiques.

## Phase 18 — CORE-01B — State Composition bout en bout

Après validation suffisante des analyseurs et adaptateurs, exécuter les fixtures CORE-01 depuis le texte naturel jusqu’au graphe final et à la réponse. Le succès exige que les résultats proviennent réellement des entités particulières, relations, hypothèses, structures temporelles et transformations composées, pas de règles ad hoc spécifiques aux phrases de test.

---

# 70. Le véritable cœur du projet

Les parseurs NLP, les formalismes de dialogue (Dynamic Syntax, KoS/TTR, ISO/DIT++, SDRT, ISU), Soar et les formalismes discursifs sont des composants importants, mais ils ne sont pas le cœur de la générativité.

Le noyau est :

```text

OBSERVATION GRAPH

        +

TRANSMISSION / PROVENANCE GRAPH

        +

LEARNED GRAPH

        +

EPISODIC MEMORY

        +

RELATIONAL TEMPORAL / EPISODIC CONTEXT

        +

PERSISTENT SITUATION / WORLD STATE

        +

STATE-TRANSFORMATION COMPOSITION

        +

STRUCTURAL INDUCTION

        +

RECURSIVE ABSTRACTION

        +

MEMORY CONSOLIDATION

        +

STRUCTURAL RETRIEVAL

        +

CROSS-REPRESENTATION SEMIOTIC LINKING

        +

FACTORIZED HYPOTHESIS MANAGEMENT

        +

JUSTIFICATION / CONTRADICTION TRACKING

        +

LAZY INTERPRETATION COMPOSITION

        +

BOUNDED DIVERSE ACTIVE BEAM

        +

CANDIDATE TRANSFORMATION GENERATION

        +

UTILITY-BASED SELECTION

        +

LEARNED INTERACTION-STATE DYNAMICS

        +

COMMUNICATIVE PLANNING

```

---

# 71. Principe directeur final

Le système ne doit pas être un chatbot à règles caché derrière une architecture complexe.

Il ne faut pas programmer :

```text

ce qu’il doit comprendre

ce qu’il doit vouloir dire

quelles catégories il doit découvrir

quelles conversations il doit reconnaître

quelles réponses il doit préférer

```

Il faut programmer :

```text

comment représenter

comment observer

comment mémoriser

comment comparer

comment conserver des hypothèses concurrentes sur plusieurs plans de représentation

comment factoriser l’incertitude sans matérialiser son produit cartésien

comment tracer supports, contradictions, dépendances et décisions historiques

comment composer paresseusement quelques interprétations globales seulement lorsqu’elles sont nécessaires

comment maintenir un beam actif borné mais structurellement diversifié

comment relier forme, phonologie, symbole, contexte et conséquences sans les confondre

comment abstraire

comment compresser

comment récupérer

comment générer des transformations

comment évaluer leurs conséquences

comment maintenir et réviser un état interactionnel

comment construire un plan communicatif à partir d’une transformation sélectionnée

comment réaliser ce plan sans y ajouter de contenu cognitif

comment apprendre de l’expérience

```

L’invariant architectural est :

> **Préservation analytique maximale, matérialisation combinatoire minimale.**

Le système doit pouvoir changer d’interprétation avec l’expérience sans réécrire ce qu’il avait observé, pensé ou sélectionné auparavant. La richesse persistante appartient au stockage factorisé ; le runtime ne matérialise qu’un petit nombre d’interprétations nécessaires au raisonnement courant.

Deux invariants supplémentaires s’appliquent :

> Le système doit pouvoir construire des objets particuliers persistants, appliquer des transformations successives à leur graphe et reconstruire l’état résultant sans règles ad hoc propres aux exemples.

> Le temps cognitif est relationnel : les dates/heures absolues restent des ancres externes de provenance et ne peuvent jamais remplacer la structure temporelle construite entre événements, états, observations, épisodes et contextes.

Le test ultime du projet est :

> Après ingestion d’un corpus suffisamment riche, le système doit nous montrer des structures utiles que nous n’avons jamais écrites, nommées ou prévues nous-mêmes.
