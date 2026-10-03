# Proposition de refonte de la couche temporelle

## Statut

Ce document ne remplace pas encore la couche temporelle de l’architecture principale.

Il formalise les problèmes identifiés, les invariants à respecter et le programme de conception à suivre avant toute modification de l’architecture.

La couche temporelle actuelle doit être considérée comme **provisoire et insuffisamment fondée**.

---

# 1. Constat

La conception temporelle actuelle repose surtout sur des outils comme :

- HeidelTime ;
- Duckling ;
- des timestamps de source ;
- des relations temporelles générales dans les épisodes.

Ces éléments peuvent produire des données utiles, mais ils ne constituent pas à eux seuls une théorie formelle du temps cognitif ou linguistique.

Le problème principal est qu’une architecture cognitive symbolique ne peut pas réduire le temps à :

```text
knowledge.heard_at = 2024-05-23T11:10:12
```

ou à une simple normalisation de surface :

```text
"hier"
    ↓
2024-05-22
```

puis utiliser cette valeur comme représentation cognitive primaire.

Une telle approche risque de contaminer tout le système avec une conception artificielle du temps fondée sur l’horloge plutôt que sur les relations entre événements, états, observations, épisodes et contextes.

---

# 2. Invariant fondamental : temporalité relationnelle

La représentation temporelle cognitive primaire doit être **relationnelle**.

Le système doit représenter principalement :

```text
Event_A
    before → Event_B

Observation_X
    during → Episode_Y

Episode_Y
    after → Episode_Z

State_S
    holds_during → Interval_I

Context_12
    succeeds → Context_11
```

Les coordonnées calendaires et horlogères externes peuvent être conservées lorsqu’elles existent, mais uniquement comme **ancres de source ou de provenance**.

Exemple :

```text
ExternalClockAnchor_17
    source = source_metadata
    value = 2024-05-23T11:10:12
```

Cette structure ne doit jamais remplacer les relations temporelles qui constituent la représentation cognitive.

---

# 3. No Temporal Normalization Collapse

Une expression temporelle ne doit jamais être réduite irréversiblement à une valeur normalisée.

Exemples :

```text
hier
avant
après
plus tard
encore
déjà
toujours
jadis
désormais
depuis
jusqu'à
aussitôt
finalement
pendant
entre-temps
à peine
venir de
être sur le point de
continuer à
cesser de
```

ainsi que leurs milliers de compositions syntaxiques et discursives.

Le système ne doit jamais être construit comme :

```python
if token == "encore":
    ...
elif token == "déjà":
    ...
elif token == "avant":
    ...
```

Les fonctions temporelles de ces formes doivent être **analysées, comparées, reliées et éventuellement induites** à partir de leurs usages.

---

# 4. Distinction obligatoire entre plusieurs temporalités

Le système doit pouvoir distinguer au minimum :

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

Ces dimensions ne doivent pas être confondues.

Par exemple :

```text
"Hier, Julie m'a dit que Paul partirait demain."
```

contient plusieurs temporalités différentes :

```text
temps de l'énonciation
temps du "hier"
temps de l'acte de parole de Julie
temps futur relatif à cet acte
temps auquel le système observe la phrase
```

Une simple date normalisée ne peut pas représenter correctement cette structure.

---

# 5. Principe de mémoire temporelle

La mémoire temporelle ne doit pas être organisée principalement autour d’horodatages absolus.

Exemple interdit comme représentation cognitive principale :

```text
Memory_8821
heard_at = 2024-05-23T11:10:12
```

Représentation privilégiée :

```text
Observation_8821
    occurred_during → Episode_441
    after → Observation_8817
    before → Observation_8830
    same_interaction_as → Conversation_73
    temporally_near → Event_932
    contextually_inside → SituationModel_18
```

Et :

```text
Episode_441
    after → Episode_440
    before → Episode_442
    overlaps → Conversation_73
```

La question :

```text
Quand est-ce que j'ai entendu P ?
```

devrait d’abord produire une reconstruction relationnelle :

```text
P
 ↓
TransmissionOccurrence_918
 ↓
Episode_B

Episode_B
    after → Episode_A
    before → Episode_C
```

Puis éventuellement :

```text
"entre la discussion avec Julie et mon départ au travail"
```

Si une ancre externe absolue existe, elle peut être utilisée ensuite pour produire une réponse calendaire précise.

---

# 6. Séparation entre quatre niveaux

La future architecture temporelle devrait distinguer explicitement quatre niveaux.

## 6.1 Ordre observable

Ce niveau ne contient pratiquement aucune théorie.

Il conserve les relations directement présentes dans l’expérience ou la source.

Exemples :

```text
Observation_A
    predecessor_of → Observation_B

Message_17
    reply_to → Message_12

Turn_3
    before_in_source → Turn_4
```

Les timestamps éventuels restent des métadonnées de provenance.

---

## 6.2 Sémantique temporelle du discours

Le système doit produire des **relations temporelles candidates** à partir des structures linguistiques.

Cette couche doit être fondée sur des théories formelles du temps, du tense, de l’aspect, de l’anaphore temporelle et du discours.

Les théories à étudier incluent notamment :

```text
DRT / Temporal DRT
SDRT
Reichenbach
event semantics
aspectual semantics
reference time
temporal anaphora
discourse relations
```

Ces formalismes doivent être utilisés comme analyseurs ou sources d’annotations structurées, jamais comme ontologie cognitive définitive.

Exemple :

```text
Event_A
Event_B

analysis_source = temporal_DRT_adapter
candidate_relation(Event_A, Event_B) = ...
```

et non :

```text
CognitiveTruth = AFTER
```

---

## 6.3 Contexte temporel épisodique

Le système doit posséder une représentation du contexte temporel de l’expérience.

Conceptuellement :

```text
Episode_88
    contains → Observation_X

Observation_X
    after → Observation_W
    before → Observation_Y
    same_local_context → Context_31

Context_31
    succeeds → Context_30
    precedes → Context_32
```

La proximité temporelle peut émerger de la structure des expériences, des séquences, de la continuité contextuelle et des transitions entre épisodes.

Cette couche doit être conçue en tenant compte des théories psychologiques et neuroscientifiques sur :

```text
episodic memory
temporal context
event segmentation
sequence memory
temporal distance
duration perception
context drift
hippocampal sequence coding
time cells
entorhinal representations
replay
```

Ces travaux ne doivent pas être transformés directement en primitives symboliques sans justification.

Ils servent à contraindre et inspirer l’architecture.

---

## 6.4 Structures temporelles apprises

Les catégories temporelles cognitives ne doivent pas être une enum prédéfinie.

Il ne faut pas hardcoder :

```text
BEFORE
AFTER
DURING
OVERLAPS
UNTIL
SINCE
STILL
ALREADY
AGAIN
SOON
LATER
...
```

comme ontologie cognitive fermée.

Même les formalismes utiles comme l’algèbre d’Allen ne doivent pas devenir automatiquement les catégories internes du système.

Ils peuvent servir comme :

```text
outil de comparaison
formalisme externe
système de contraintes
analyseur
langage de test
```

mais le Learned Graph doit pouvoir induire ses propres structures anonymes :

```text
Pattern_183
Pattern_922
Transformation_72
```

Exemple :

```text
A puis B
A puis B
A puis B
```

peut conduire à :

```text
Pattern_771

conditions structurelles:
    X apparaît entre deux propositions A et B

régularité:
    la structure associée à B suit régulièrement celle associée à A
```

Un humain pourra éventuellement reconnaître cette structure comme une relation temporelle de succession.

Le système n’a pas besoin qu’on lui fournisse ce nom.

---

# 7. Le temps comme pouvoir relationnel des termes

Les termes temporels doivent être considérés comme des éléments pouvant modifier, relier ou contraindre des structures déjà présentes.

Exemple :

```text
plus tard
```

ne doit pas être réduit à une date.

Il peut agir comme une structure qui relie :

```text
Event_B
```

à :

```text
Event_A
```

selon le contexte discursif courant.

De même :

```text
encore
déjà
toujours
depuis
venir de
continuer à
```

peuvent modifier :

```text
état courant
persistance
répétition
frontière temporelle
relation entre événements
référence temporelle
présuppositions temporelles
```

sans qu’un sens final soit hardcodé.

Le système doit apprendre leurs effets à partir de leurs structures linguistiques, contextes d’utilisation et conséquences observées.

---

# 8. Relation avec le moteur d’état

La couche temporelle doit être distincte mais fortement intégrée au futur moteur CORE-01.

Le moteur d’état traite :

```text
state S0
    ↓ event E1
state S1
    ↓ event E2
state S2
```

La couche temporelle doit fournir les contraintes permettant de savoir :

```text
quel événement précède lequel
quels états persistent
quand une transformation devient applicable
quelles observations appartiennent au même épisode
quelles relations temporelles restent ambiguës
```

Exemple :

```text
Julie allume la lampe.
Elle la laisse allumée.
Deux heures plus tard, elle l'éteint.
```

Le système doit conserver :

```text
Event_1
Event_2
Event_3

relations temporelles candidates
relations de persistance
transformations d'état
```

sans réduire tout le raisonnement à des timestamps.

---

# 9. Statut des outils actuels

## 9.1 HeidelTime

HeidelTime ne doit plus être considéré comme la couche temporelle elle-même.

Il peut éventuellement servir comme analyseur externe quarantainé pour identifier :

```text
expressions temporelles
types d'expressions
spans
valeurs proposées
```

mais ses normalisations ne doivent jamais devenir directement des représentations cognitives.

---

## 9.2 Duckling

Même principe.

Duckling peut fournir :

```text
durée
intervalle
nombre
mesure
grain
candidats de normalisation
```

mais les sorties doivent rester :

```text
analysis_source = Duckling
```

et ne jamais écraser la structure relationnelle issue du discours.

---

## 9.3 Critère d'acceptation futur d'un outil temporel

Avant d’ajouter un outil à l’architecture, il faut répondre à :

> Est-ce que cet outil préserve les relations temporelles sémantiques de l’expression, ou les réduit-il à une valeur canonique ?

Si l’outil effectue une réduction, il doit être possible de :

```text
conserver la forme originale
conserver les relations candidates
conserver la provenance de l'analyse
isoler la normalisation
ne jamais imposer cette normalisation au Learned Graph
```

Sinon, l’outil doit être rejeté.

---

# 10. Fondations scientifiques à étudier avant modification de l’architecture

Un document de recherche dédié doit précéder toute implémentation définitive.

Il doit étudier systématiquement :

## Formal linguistics

```text
DRT / Temporal DRT
SDRT
Reichenbach
tense semantics
aspect semantics
event semantics
temporal anaphora
reference time
temporal discourse relations
```

## Psychology

```text
episodic memory
temporal context models
event segmentation
sequence memory
duration perception
temporal distance
contextual drift
memory reconstruction
```

## Neuroscience

```text
hippocampus
time cells
entorhinal cortex
sequence coding
context coding
replay
event boundaries
multi-scale temporal representation
```

## Formal computation

```text
relation graphs
constraint propagation
interval reasoning
state persistence
temporal uncertainty
partial ordering
incremental graph updates
lazy temporal composition
```

---

# 11. Grille d’évaluation des mécanismes proposés

Chaque mécanisme envisagé doit être documenté avec :

```text
nom du mécanisme
source théorique ou empirique
ce qu'il affirme exactement
type de données en entrée
structure produite
niveau de certitude
catégories hardcodées nécessaires
relations hardcodées nécessaires
compatibilité avec l'induction
compatibilité avec l'Observation Graph
compatibilité avec le Learned Graph
risque de contamination ontologique
acceptable / rejeté / à étudier
```

Aucun mécanisme temporel ne doit entrer dans l’architecture sans cette analyse.

---

# 12. Modifications proposées à l’architecture

## 12.1 Déclasser la couche temporelle actuelle

La section temporelle actuelle basée principalement sur :

```text
HeidelTime
Duckling
```

ne doit plus être présentée comme le modèle temporel du système.

Elle doit être renommée comme quelque chose du type :

```text
External Temporal Surface Analyzers
```

ou équivalent.

---

## 12.2 Introduire un futur Temporal / Episodic Relation Subsystem

L’architecture devra probablement recevoir un sous-système explicite dont la structure générale sera approximativement :

```text
SOURCE ORDER
    ↓
LINGUISTIC TEMPORAL ANALYSES
    ↓
TEMPORAL RELATION CANDIDATES
    ↓
EPISODIC TEMPORAL CONTEXT
    ↓
FACTORISED TEMPORAL HYPOTHESES
    ↓
CONSTRAINT PROPAGATION
    ↓
LEARNED TEMPORAL STRUCTURES
    ↓
ACTIVE SITUATION MODEL
```

Cette structure reste provisoire tant que l’étude théorique n’est pas terminée.

---

## 12.3 Séparer strictement les ancres absolues

Créer un espace explicite pour :

```text
ExternalClockAnchor
ExternalCalendarAnchor
SourceTimestamp
DocumentCreationTime
```

Ces structures appartiennent à :

```text
Source Graph
Transmission / Provenance Graph
```

et non au Learned Graph comme primitives temporelles.

---

## 12.4 Ajouter un invariant architectural explicite

### Temporal Relationality Invariant

> Toute information temporelle cognitive doit être représentée principalement par des relations entre événements, états, observations, épisodes ou contextes. Les coordonnées calendaires ou horlogères externes peuvent être conservées uniquement comme ancres de provenance et ne doivent jamais remplacer les relations temporelles à partir desquelles elles ont été obtenues.

### No Temporal Normalization Collapse

> Une expression temporelle ne doit jamais être réduite irréversiblement à une coordonnée normalisée. Sa forme, son contexte, ses relations candidates, ses ambiguïtés et sa provenance doivent rester disponibles.

---

# 13. Modifications proposées aux POC

Les POC actuelles :

```text
TIME-01 — HeidelTime
TIME-02 — Duckling
TIME-03 — Coexistence HeidelTime / Duckling
```

doivent être considérées comme provisoires.

Elles ne doivent pas être implémentées telles quelles avant la refonte.

Elles pourront devenir des POC d’analyseurs externes, mais ne devront plus représenter le cœur temporel.

De nouvelles POC seront nécessaires pour tester au minimum :

```text
ordre observable
relations temporelles discursives
anaphore temporelle
temps de référence
aspect
relations événements / états
séquences d'épisodes
contexte temporel
ambiguïtés temporelles
révision temporelle
persistance des états
induction de patterns temporels
rappel temporel relationnel
liaison facultative vers des ancres calendaires externes
```

---

# 14. Exemple cible : « quand est-ce que j'ai entendu ça ? »

Supposons :

```text
Episode_A:
    discussion avec Julie

Episode_B:
    quelqu'un me dit P

Episode_C:
    départ au travail

Episode_D:
    apprentissage de Q
```

Le contenu P est lié à :

```text
TransmissionOccurrence_918
    content → P
    contained_in → Episode_B
```

et :

```text
Episode_B
    after → Episode_A
    before → Episode_C
```

La première réponse reconstruite peut être :

```text
"après la discussion avec Julie et avant mon départ au travail"
```

Si une source externe contient aussi :

```text
ExternalClockAnchor
    attached_to → Episode_B
    value = 2024-05-23T11:10:12
```

alors une réponse calendaire précise peut également être fournie.

Mais le graphe temporel n’est jamais réduit à cette valeur.

---

# 15. Prudence scientifique

Il ne faut pas prétendre que :

> le cerveau ne stocke jamais de temps absolu.

Cette affirmation serait trop forte.

Les données scientifiques soutiennent plutôt l’importance de :

```text
séquence
contexte
ordre
événements
durée
transitions
représentations temporelles à plusieurs échelles
```

dans la mémoire et la cognition temporelle.

La décision de privilégier une représentation relationnelle est donc :

```text
un choix architectural
+
une contrainte de cohérence avec les données cognitives
```

et non une reproduction démontrée du mécanisme neuronal exact.

---

# 16. Décision immédiate

Avant toute modification définitive de l’architecture :

1. ne pas implémenter la couche temporelle actuelle comme si elle était définitive ;
2. ne pas faire de HeidelTime/Duckling le cœur temporel ;
3. ne pas introduire de timestamps comme représentation cognitive primaire ;
4. réaliser une étude dédiée linguistique + psychologie + neuroscience + computation ;
5. évaluer chaque mécanisme avec la grille définie plus haut ;
6. seulement ensuite modifier l’architecture et les POC temporelles ;
7. intégrer la nouvelle couche avec CORE-01 et le futur Situation Model.

---

# Principe directeur

> Le temps n’est pas une propriété numérique attachée aux connaissances.

> Le temps est une structure relationnelle construite à partir de l’ordre, des événements, des états, des contextes, des transmissions et des transformations observées.

> Les formes linguistiques temporelles participent à construire et modifier cette structure.

> Les catégories temporelles internes doivent être apprises autant que possible, et non imposées sous forme d’une ontologie prédéfinie.
