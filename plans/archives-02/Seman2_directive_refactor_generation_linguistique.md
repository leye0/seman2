# Seman2 — Directive de refactorisation de la génération linguistique

## Objet du document

Ce document définit la prochaine correction architecturale à appliquer à Seman2.

La cible n’est pas de « rendre les phrases un peu plus jolies ». La cible est de **retirer progressivement du runtime cognitif toute connaissance spécifique de structures de phrases anglaises**, afin que Seman2 puisse produire des énoncés nouveaux à partir de représentations sémantiques, sans multiplier les templates Python/Java.

Le runtime actuel de SYS-10 doit être considéré comme un **scaffolding d’intégration end-to-end**. Il prouve que la chaîne cognition → décision → réponse → réingestion fonctionne, mais il ne doit pas être généralisé tel quel.

La direction à prendre est :

```text
cognition
  ↓
plan communicatif abstrait
  ↓
plan sémantico-linguistique
  ↓
MRS cible
  ↓
ERG / ACE en génération
  ↓
plusieurs réalisations grammaticales
  ↓
ranking
  ↓
surface choisie
  ↓
réingestion L0
```

SimpleNLG doit devenir une baseline/fallback, pas le générateur principal.

---

# 1. Problème à corriger immédiatement

Le runtime de SYS-10 mélange actuellement trois responsabilités qui doivent être séparées :

1. **décider quoi dire**;
2. **décider comment représenter linguistiquement ce contenu**;
3. **réaliser grammaticalement la phrase anglaise**.

Aujourd’hui, certaines décisions de niveau 2 et 3 sont déjà prises en Python.

Exemples actuels :

```text
supported
  → subject
  → verb
  → preposition
  → object
```

```text
ambiguous
  → copula = "be"
  → coordinator = "or"
  → deux options
```

```text
unknown
  → subject = "I"
  → verb = "know"
  → negated = True
```

Ce pattern ne doit pas être étendu.

Interdiction architecturale à partir de maintenant :

```text
NE PAS ajouter :
  answer-color
  answer-owner
  answer-time
  answer-reason
  answer-quantity
  answer-belief
  answer-property
  answer-comparison
  etc.

sous forme de nouvelles branches syntaxiques codées à la main.
```

Le système doit pouvoir répondre à de nouveaux contenus **sans exiger l’ajout d’un nouveau template de phrase**.

---

# 2. Invariant central à introduire

Séparer strictement :

```text
WHAT TO SAY
```

de :

```text
HOW TO SAY IT
```

## 2.1 WHAT TO SAY

Le système cognitif décide :

```text
intent
contenu propositionnel
contexte épistémique
source
provenance
degré de confiance
interlocuteur
QUD
objectif discursif
contenus obligatoires
contenus interdits
```

## 2.2 HOW TO SAY IT

Une couche linguistique distincte décide :

```text
lexicalisation
temps
aspect
mood
polarité
définitude
quantification
pronominalisation
ordre informationnel
focus
topic
coordination
subordination
relation discursive
```

Puis ERG/ACE réalise la grammaire.

---

# 3. État actuel à considérer comme baseline uniquement

Les composants suivants doivent être conservés pour l’instant afin de maintenir les tests SYS-10 existants :

```text
ResponseController
ResponseController._plan_content()
SimpleNLGRealizer
Seman2SimpleNLGRealizer.java
AutobiographicalRetriever
AutobiographicalRetriever._query_frame()
AutobiographicalRetriever._match_location()
```

Ne pas les supprimer immédiatement.

Les marquer conceptuellement comme :

```text
SYS-10 legacy baseline
```

Ils servent à :

- vérifier les régressions;
- garder une chaîne end-to-end fonctionnelle;
- comparer la nouvelle architecture à l’ancienne;
- diagnostiquer les divergences.

Le nouveau chemin doit être construit **en parallèle**, puis devenir le chemin principal seulement lorsque les critères de sortie définis plus bas sont satisfaits.

---

# 4. Nouveau découpage des responsabilités

Créer quatre couches distinctes.

```text
L6A  CommunicativePlan
L6B  SemanticRealizationPlan
L6C  GenerableMRS
L7A  RealizationCandidates
L7B  RankedRealization
L7C  RealizedTurn
```

Il n’est pas obligatoire de changer les numéros L6/L7 globaux du projet. Les suffixes servent ici à rendre les responsabilités explicites.

---

# 5. L6A — CommunicativePlan

## 5.1 But

Le plan communicatif doit décrire **ce que le système veut communiquer**, sans contenir de syntaxe anglaise inutile.

Exemple cible :

```json
{
  "intent": "answer",
  "speech_act": "assert",
  "qud_ref": "qud:123",
  "propositions": [
    {
      "relation": "location",
      "theme_ref": "entity:apple",
      "location_ref": "entity:basket",
      "status": "supported",
      "confidence": 0.94
    }
  ],
  "qualification": null,
  "evidence_refs": [
    "episode:45",
    "relation:998"
  ],
  "must_express": [
    "proposition:location"
  ],
  "must_not_assert": [],
  "dialogue_goal": "resolve-qud"
}
```

## 5.2 Ce qui ne doit plus être présent à ce niveau

Éviter :

```json
{
  "subject": "...",
  "verb": "...",
  "preposition": "...",
  "object": "...",
  "copula": "be",
  "coordinator": "or"
}
```

sauf si un élément lexical précis est lui-même une donnée sémantique ou discursive nécessaire.

---

# 6. Modifier `ResponseController`

## 6.1 Rôle cible

`ResponseController` doit :

1. recevoir le résultat du retrieval;
2. recevoir l’état dialogique;
3. demander à Soar de choisir une stratégie;
4. construire un `CommunicativePlan`;
5. **ne plus construire lui-même une structure syntaxique anglaise**.

## 6.2 Refactor de `_plan_content()`

La fonction actuelle `_plan_content()` ne doit plus retourner une structure orientée SimpleNLG.

Remplacer progressivement :

```text
subject
verb
preposition
object
copula
coordinator
```

par des objets sémantiques.

Exemple :

```text
ancien :
{
  intent: answer-location,
  subject: ...,
  verb: ...,
  preposition: ...,
  object: ...
}
```

devient :

```text
nouveau :
{
  intent: answer,
  speech_act: assert,
  proposition: {
    predicate_family: spatial-location,
    theme_ref: ...,
    ground_ref: ...,
    relation_ref: ...
  }
}
```

Le contrôleur ne doit pas savoir si l’anglais final utilisera :

```text
is in
lies in
can be found in
inside ...
```

Le choix doit être fait plus bas.

---

# 7. Introduire `SemanticRealizationPlanner`

Créer un composant dédié.

Nom recommandé :

```text
SemanticRealizationPlanner
```

Emplacement recommandé :

```text
seman2_runtime/semantic_realization.py
```

ou module équivalent cohérent avec l’organisation actuelle.

## 7.1 Entrées

```text
CommunicativePlan
DialogueState
DiscourseMemory
IdentityBeam
TemporalMemory
active referents
learned preferences
```

## 7.2 Sortie

Un artefact :

```text
semantic-realization-plan
```

contenant les décisions linguistiques nécessaires à la construction d’un MRS, mais **pas une chaîne de caractères finale**.

Exemple :

```json
{
  "plan_ref": "communicative-plan:...",
  "speech_act": "assert",
  "semantic_content": [...],
  "lexicalization_candidates": [...],
  "reference_choices": [...],
  "tense": "present",
  "aspect": null,
  "polarity": "positive",
  "information_structure": {
    "topic_ref": "entity:apple",
    "focus_ref": "entity:basket"
  },
  "discourse_relations": [],
  "constraints": {
    "must_preserve_epistemic_status": true,
    "must_preserve_source_attribution": true
  }
}
```

---

# 8. Ne pas coder un mapping sémantique → phrase

Le `SemanticRealizationPlanner` peut contenir des règles de traduction entre représentations cognitives et représentations sémantiques linguistiques.

Il ne doit pas contenir :

```python
if relation == "location":
    return f"{subject} is in {object}"
```

Il peut contenir :

```text
relation cognitive LOCATION
  → rechercher les prédicats ERG/MRS compatibles
  → produire une ou plusieurs lexicalisations candidates
```

Exemple :

```text
LOCATION(theme, ground)
```

peut donner des candidats de représentation linguistique :

```text
_in_p_rel
_inside_p_rel
_loc_nonsp_rel
```

selon les contraintes réellement supportées par ERG.

Ces mappings doivent être :

- explicites;
- testables;
- documentés;
- indépendants de l’ordre final des mots;
- basés sur les représentations MRS/ERG disponibles.

---

# 9. Introduire `MRSBuilder`

Créer un composant séparé :

```text
MRSBuilder
```

But :

```text
SemanticRealizationPlan
  ↓
MRS générable par ERG
```

## 9.1 Responsabilités

Le composant doit construire :

```text
relations
handles
variables
features
quantifiers
scope constraints
index
top handle
```

selon les exigences MRS.

Il doit pouvoir produire un MRS **sans repartir de la phrase originale**.

C’est un critère fondamental.

---

# 10. Première preuve obligatoire : round-trip

Avant toute migration complète, implémenter un POC minimal.

## Test A

```text
surface
  ↓
ERG parse
  ↓
MRS
  ↓
ACE generate
  ↓
surface candidate
```

Corpus minimal :

```text
The apple is in the basket.
Maya opened the door.
Amira carried the notebook.
The notebook was blue.
Where is the apple?
Did Maya open the door?
```

Objectifs :

- confirmer la chaîne ACE generation;
- inspecter les MRS réellement générables;
- comprendre les contraintes ERG;
- identifier les différences entre MRS de parsing et MRS utilisables en génération.

---

# 11. Deuxième preuve obligatoire : génération depuis Seman2

Construire ensuite un MRS depuis les structures internes.

Exemple entrée :

```text
entity:apple
entity:basket
relation:
  type = location
  theme = apple
  ground = basket
```

Aucune surface source ne doit être utilisée.

Sortie attendue :

```text
MRS
  ↓
ACE
  ↓
The apple is in the basket.
```

Le test échoue si le code récupère secrètement :

- la phrase d’origine;
- un template;
- une chaîne stockée;
- un exemple du corpus.

---

# 12. Introduire `ACERealizer`

Créer :

```text
ACERealizer
```

But :

```text
GenerableMRS
  ↓
ACE / ERG
  ↓
ensemble de réalisations
```

La sortie ne doit pas être une phrase unique.

Créer un artefact :

```text
realization-candidate-set
```

Exemple :

```json
{
  "mrs_ref": "...",
  "candidates": [
    {
      "surface": "...",
      "derivation": "...",
      "ace_score": -4.21,
      "rank": 1
    },
    {
      "surface": "...",
      "derivation": "...",
      "ace_score": -5.31,
      "rank": 2
    }
  ]
}
```

Conserver les scores ERG/ACE disponibles.

---

# 13. Introduire `SurfaceRanker`

Créer une abstraction stable :

```text
SurfaceRanker
```

avec au moins deux implémentations.

## 13.1 `ERGBaselineRanker`

Utilise uniquement le ranking natif fourni par ERG/ACE.

## 13.2 `LearnedSurfaceRanker`

Ajoute progressivement des préférences apprises par Seman2.

Interface cible :

```text
rank(
    semantic_plan,
    dialogue_context,
    candidate_set,
    learned_preferences
)
→ ranked_candidate_set
```

---

# 14. Apprentissage des préférences de réalisation

Ne pas entraîner Seman2 à réapprendre toute la grammaire.

Considérer :

```text
ERG = espace grammatical autorisé
```

et :

```text
apprentissage Seman2 = préférences parmi les formes autorisées
```

Le modèle doit apprendre :

```text
P(realization | semantics, discourse, biography)
```

ou une approximation algorithmique inspectable équivalente.

Le modèle peut être :

- MaxEnt;
- log-linéaire;
- ranking pairwise;
- comptage pondéré;
- règles apprises;
- autre modèle non neuronal inspectable.

La priorité est l’architecture, pas le choix définitif de l’algorithme.

---

# 15. Données d’entraînement du ranking

Chaque expérience linguistique ingérée peut fournir :

```text
surface réellement observée
MRS analysé
contexte dialogique
QUD
référents actifs
registre
locuteur
acte discursif estimé
```

Pipeline d’apprentissage :

```text
surface observée
  ↓
ERG parse
  ↓
MRS
  ↓
ACE generate(MRS)
  ↓
ensemble de variantes grammaticales
  ↓
identifier la surface observée ou sa dérivation
  ↓
extraire features
  ↓
mettre à jour le ranking
```

Si la surface observée n’est pas reproduite exactement :

- ne pas forcer une équivalence;
- conserver le cas;
- vérifier si la cause est :
  - couverture ERG;
  - tokenisation;
  - MRS non réversible;
  - construction absente;
  - différence orthographique;
  - différence stylistique.

---

# 16. Features initiales recommandées

Commencer avec un ensemble petit et inspectable.

```text
sentence_length
syntactic_depth
number_of_clauses
number_of_pronouns
number_of_full_NPs
active_vs_passive
definite_vs_indefinite
subject_given
subject_new
object_given
object_new
topic_continuity
focus_position
coordination_count
subordination_count
contraction_used
negation_used
epistemic_marker_used
dialogue_act
qud_alignment
```

Ne pas commencer avec des centaines de features.

Le but initial est de prouver que le système peut apprendre une préférence de surface sans template manuel.

---

# 17. Apprendre la pronominalisation

Ne pas encoder globalement :

```text
si référent récent → "it"
```

Créer une décision explicite de référence.

Entrées :

```text
salience
distance
ambiguity
gender
number
grammatical role
QUD
contrast
last mention form
dialogue context
```

Sortie candidate :

```text
full NP
definite NP
demonstrative
pronoun
proper name
```

Le ranking peut apprendre progressivement les préférences.

ERG réalise ensuite la forme grammaticale.

---

# 18. Apprendre les marqueurs épistémiques

Le système possède déjà des états comme :

```text
supported
ambiguous
unknown
weak
probable
```

Ne pas faire :

```python
if confidence < 0.8:
    prepend("I think")
```

Créer plutôt plusieurs stratégies sémantico-discursives candidates :

```text
assert
hedged-assert
state-uncertainty
request-clarification
partial-answer
```

Puis générer leurs réalisations et choisir.

Exemples possibles :

```text
The apple is in the basket.
I think the apple is in the basket.
The apple is probably in the basket.
It may be in the basket.
```

Le runtime cognitif choisit le degré d’engagement.

La couche linguistique choisit la réalisation.

---

# 19. Corriger le hardcoding du retrieval

Le `AutobiographicalRetriever` actuel est spécialisé sur les localisations.

Ne pas étendre la stratégie actuelle par duplication.

Interdit :

```text
_match_location
_match_color
_match_owner
_match_time
_match_reason
_match_quantity
...
```

---

# 20. Introduire une requête relationnelle générique

Créer une représentation de requête sémantique.

Exemple :

```json
{
  "query_type": "relation-value",
  "target_relation_family": "location",
  "constraints": [
    {
      "role": "theme",
      "entity_ref": "entity:apple"
    }
  ],
  "requested_role": "ground"
}
```

Pour une couleur :

```json
{
  "query_type": "property-value",
  "target_relation_family": "color",
  "constraints": [
    {
      "role": "entity",
      "entity_ref": "entity:apple"
    }
  ],
  "requested_role": "value"
}
```

Le moteur de retrieval doit manipuler :

```text
relations
rôles
variables
contraintes
identités
contexts
provenance
```

et non une fonction par type de question.

---

# 21. Généraliser `AutobiographicalRetriever`

Plan de migration :

## Étape 1

Conserver `_match_location()` comme test de référence.

## Étape 2

Introduire :

```text
QueryFrame
QueryConstraint
RelationPattern
BindingCandidate
AnswerProjection
```

## Étape 3

Implémenter un moteur générique :

```text
match_query_frame(query_frame, cognitive_candidate)
```

## Étape 4

Faire passer les tests locatifs existants avec le moteur générique.

## Étape 5

Retirer la dépendance fonctionnelle à `_match_location()`.

Ne supprimer l’ancien code qu’après équivalence comportementale.

---

# 22. Corriger le faux choix Soar actuel

Actuellement, Python associe directement :

```text
supported → answer
unknown → ignorance
ambiguous → clarification
```

et construit un beam où le choix désiré est déjà dominant.

Cela doit rester un test SYS-10, pas l’architecture définitive.

---

# 23. Introduire de vrais opérateurs concurrents

Pour une situation ambiguë, Soar doit pouvoir comparer :

```text
retrieve-more
answer-with-qualification
request-clarification
state-ambiguity
partial-answer
defer
```

Pour une situation inconnue :

```text
retrieve-more
search-other-memory
ask-context
acknowledge-ignorance
answer-partially
```

Pour une situation soutenue :

```text
answer-directly
answer-with-evidence
answer-with-qualification
summarize
```

Chaque opérateur doit avoir :

```text
preconditions
expected benefit
cost
risk
required evidence
budget effect
```

---

# 24. Soar ne doit pas choisir des structures de phrases

Soar choisit :

```text
communicative strategy
```

et non :

```text
syntax template
```

Exemple :

```text
Soar:
  choose request-clarification
```

Puis :

```text
SemanticRealizationPlanner:
  construct clarification semantics
```

Puis :

```text
ERG:
  realize grammatical options
```

---

# 25. Créer des contrats d’artefacts supplémentaires

Ajouter des types d’artefacts explicites.

Recommandation :

```text
semantic-realization-plan
generable-mrs
realization-candidate-set
ranked-realization-set
```

## `semantic-realization-plan`

Champs minimaux :

```text
communicative_plan_ref
semantic_content
reference_choices
tense
aspect
mood
polarity
information_structure
discourse_relations
epistemic_constraints
```

## `generable-mrs`

```text
semantic_plan_ref
mrs
mrs_hash
grammar_build
validation_status
```

## `realization-candidate-set`

```text
mrs_ref
candidate_surfaces
derivations
native_scores
generation_metadata
```

## `ranked-realization-set`

```text
candidate_set_ref
ranking_model_ref
ranked_candidates
selected_candidate_ref
feature_trace
```

---

# 26. Provenance obligatoire

Chaque phrase produite doit rester traçable :

```text
surface
  ↓
selected realization
  ↓
candidate set
  ↓
MRS
  ↓
semantic realization plan
  ↓
communicative plan
  ↓
retrieval / reasoning / evidence
```

On doit pouvoir répondre à :

```text
Pourquoi ce mot est présent ?
Pourquoi cette proposition est présente ?
Pourquoi cette phrase affirme-t-elle cela ?
Quelle mémoire a fourni l’information ?
Quelle décision a choisi de la communiquer ?
Quelle réalisation grammaticale a été retenue ?
Pourquoi celle-ci plutôt qu’une autre ?
```

---

# 27. Vérification anti-hallucination de surface

Avant de publier `realized-turn`, vérifier que la réalisation n’a pas ajouté de contenu propositionnel interdit.

Implémentation recommandée :

```text
surface choisie
  ↓
réanalyse ERG
  ↓
MRS de la sortie
  ↓
comparaison avec MRS cible
```

Créer un test :

```text
semantic_equivalence_check
```

ou, au minimum :

```text
semantic_coverage_check
```

La sortie doit satisfaire :

```text
toutes les propositions obligatoires sont présentes
aucune proposition substantielle non autorisée n’est ajoutée
polarité conservée
modalité conservée
attribution conservée
statut épistémique conservé
```

---

# 28. Boucle de production recommandée

La production devient :

```text
1. retrieval
2. Soar choisit une stratégie
3. CommunicativePlan
4. SemanticRealizationPlanner
5. MRSBuilder
6. ACERealizer
7. SurfaceRanker
8. sélectionner candidat
9. reparse avec ERG
10. vérifier fidélité
11. publier RealizedTurn
12. réingérer L0
```

Si aucune réalisation ne passe la vérification :

```text
ne pas fabriquer une phrase manuellement
```

Faire l’un des choix suivants :

```text
essayer une lexicalisation différente
simplifier le plan
fractionner en plusieurs clauses
fallback SimpleNLG
déclarer une impossibilité de réalisation
```

---

# 29. Maintenir SimpleNLG comme baseline

Renommer conceptuellement le chemin actuel :

```text
legacy-simple-nlg
```

Ne pas l’utiliser pour apprendre des préférences.

Il doit servir à :

```text
baseline
fallback
diagnostic
comparaison
tests de continuité
```

Ajouter dans les artefacts :

```text
realization_backend:
  erg-ace
  simplenlg-fallback
```

---

# 30. Politique de fallback

Ordre recommandé :

```text
1. ERG/ACE normal
2. ERG/ACE avec plan simplifié
3. ERG/ACE avec lexicalisation alternative
4. SimpleNLG baseline
5. non-réalisation explicite
```

Ne jamais contourner la cognition en appelant un LLM externe pour écrire la réponse.

---

# 31. Roadmap d’implémentation

## Phase R0 — Geler la baseline

- ajouter tests snapshot SYS-10;
- préserver les sorties actuelles;
- documenter les fonctions legacy;
- interdire l’ajout de nouveaux templates.

Livrable :

```text
baseline verte
```

---

## Phase R1 — POC ACE génération

- appeler ACE en mode génération;
- MRS parsé → génération;
- enregistrer toutes les réalisations;
- enregistrer dérivations et scores.

Livrable :

```text
ACERealizer minimal
```

---

## Phase R2 — MRS synthétique depuis Seman2

- construire un MRS sans surface source;
- commencer par :
  - propriété;
  - localisation;
  - action transitive simple;
- valider avec ACE.

Livrable :

```text
MRSBuilder minimal
```

---

## Phase R3 — Nouveau plan communicatif abstrait

- retirer progressivement les champs syntaxiques de `_plan_content()`;
- produire relations et propositions;
- préserver provenance et statut épistémique.

Livrable :

```text
CommunicativePlan v2
```

---

## Phase R4 — SemanticRealizationPlanner

- lexicalisation;
- tense;
- polarity;
- reference form;
- information structure;
- sortie MRS-ready.

Livrable :

```text
semantic-realization-plan
```

---

## Phase R5 — Candidate generation

- générer N surfaces;
- borner N;
- conserver tous les candidats;
- conserver scores natifs.

Valeur de départ :

```text
max_candidates = 16
```

Ajustable plus tard.

---

## Phase R6 — Ranking baseline

- utiliser score ERG;
- ajouter quelques features Seman2;
- produire trace complète du ranking.

---

## Phase R7 — Learned ranking

- créer un corpus d’apprentissage depuis les expériences;
- entraîner un premier modèle;
- versionner le modèle;
- mesurer sur probes cachés.

---

## Phase R8 — Retrieval générique

- introduire QueryFrame;
- remplacer `_match_location()` par matching générique;
- faire passer les tests locatifs;
- ajouter propriété, possession, temps.

---

## Phase R9 — Soar réellement décisionnel

- plusieurs opérateurs plausibles;
- coûts réels;
- retrieval supplémentaire;
- clarification non prédéterminée.

---

## Phase R10 — Désactivation progressive du legacy

Conditions :

```text
nouveau chemin couvre les tests SYS-10
nouveau chemin produit au moins autant de cas
aucune régression de provenance
aucune fuite externe
fallback testé
```

Alors seulement :

```text
ERG/ACE devient backend par défaut
SimpleNLG devient fallback
```

---

# 32. Tests obligatoires

Créer au minimum les suites suivantes.

## 32.1 Round-trip grammar

```text
surface → MRS → generation
```

## 32.2 Semantic construction

```text
cognition → MRS
```

sans surface source.

## 32.3 Semantic fidelity

```text
plan → surface → reparse
```

doit préserver le contenu.

## 32.4 Novel combination

Exemples tenus à l’écart :

```text
Lina put the red key in the wooden box.
```

Les participants et combinaisons ne doivent pas avoir été vus ensemble.

## 32.5 Dialogue-dependent realization

Même proposition, QUD différente.

Exemple :

```text
Q: Where is the apple?
A: In the basket.
```

versus :

```text
Q: What is in the basket?
A: The apple is.
```

selon ce qu’ERG permet réellement.

Le test doit vérifier que le contexte peut influencer la sélection de surface.

## 32.6 Epistemic preservation

```text
probable(P)
```

ne doit pas devenir :

```text
certain(P)
```

## 32.7 Attribution preservation

```text
Amira says(P)
```

ne doit pas devenir :

```text
P
```

sans attribution.

## 32.8 Negation preservation

```text
not(P)
```

ne doit pas devenir :

```text
P
```

## 32.9 Ambiguity

Si deux MRS ou deux plans restent admissibles :

```text
ne pas sélectionner silencieusement une vérité
```

## 32.10 No-template test

Ajouter un contenu nouveau.

Le test réussit seulement si aucune nouvelle branche spécifique n’est ajoutée au realizer.

---

# 33. Tests négatifs

Ajouter des garde-fous automatiques.

Recherche statique possible dans le code :

```text
"answer-location"
"answer-color"
"answer-owner"
"answer-time"
```

Le test doit empêcher la prolifération de nouveaux intents syntaxiques hyperspécifiques.

Les intents acceptables sont plus généraux :

```text
answer
clarify
acknowledge-ignorance
contrast
qualify
correct
confirm
deny
ask
```

Le contenu précis appartient aux propositions.

---

# 34. Critères de sortie de SYS-10R

SYS-10R est GO seulement si :

1. une surface nouvelle peut être produite sans template dédié;
2. le contenu cognitif peut être converti en MRS sans phrase source;
3. ACE produit plusieurs candidats dans au moins certains cas;
4. le candidat sélectionné est traçable;
5. la sortie réanalysée reste compatible avec le plan;
6. l’incertitude est préservée;
7. l’attribution est préservée;
8. la négation est préservée;
9. la génération fonctionne sur des combinaisons tenues à l’écart;
10. le système reste entièrement algorithmique;
11. aucun LLM externe n’est requis;
12. le chemin SimpleNLG peut rester uniquement en fallback;
13. le retrieval n’exige plus une fonction par type de propriété;
14. Soar commence à arbitrer entre de vrais opérateurs concurrents.

---

# 35. Ce qu’il ne faut surtout pas faire

Ne pas corriger le problème en ajoutant simplement une bibliothèque de templates plus riche.

Ne pas remplacer SimpleNLG par une autre bibliothèque qui demande toujours :

```text
subject
verb
object
```

et appeler cela une architecture générale.

Ne pas utiliser un LLM comme surface realizer caché.

Ne pas apprendre des phrases entières par cœur.

Ne pas stocker :

```text
question pattern → response pattern
```

comme mécanisme principal.

Ne pas spécialiser le runtime pour chaque propriété du monde.

Ne pas faire de Soar un simple validateur d’un choix déjà imposé.

---

# 36. Tangente architecturale à retenir

La direction générale de Seman2 devient :

```text
SYMBOLIC COGNITION
    ↓
COMMUNICATIVE INTENTION
    ↓
SEMANTIC LINGUISTIC PLAN
    ↓
MRS
    ↓
ERG / ACE
    ↓
GRAMMATICAL CANDIDATES
    ↓
LEARNED RANKING
    ↓
SURFACE
```

Le rôle de l’apprentissage est :

```text
apprendre les préférences
apprendre les usages
apprendre les choix discursifs
apprendre les habitudes
```

et non :

```text
réinventer toute la grammaire
```

---

# 37. Décision de projet

À partir de maintenant :

```text
Le code actuel de génération SYS-10 est une baseline de validation,
pas la solution de production finale.
```

La prochaine passe de développement doit donc prioriser :

```text
1. génération ERG/ACE;
2. construction MRS depuis les structures Seman2;
3. séparation plan communicatif / plan linguistique;
4. ranking de réalisations;
5. apprentissage de préférences;
6. retrieval générique;
7. décision Soar réellement ouverte.
```

Les développements qui ajouteraient simplement de nouvelles branches syntaxiques à `ResponseController` ou `SimpleNLGRealizer` doivent être évités, sauf pour maintenir temporairement un test existant.

---

# 38. Résultat attendu à terme

Un nouveau contenu doit pouvoir traverser le système ainsi :

```text
nouvelle connaissance interne
  ↓
nouvelle question
  ↓
retrieval relationnel
  ↓
Soar choisit quoi communiquer
  ↓
CommunicativePlan
  ↓
SemanticRealizationPlanner
  ↓
MRSBuilder
  ↓
ACERealizer
  ↓
16 candidats grammaticaux maximum
  ↓
SurfaceRanker
  ↓
candidat choisi
  ↓
reparse + validation
  ↓
RealizedTurn
```

et aucun développeur ne devrait avoir à ajouter :

```python
if question_type == "new_case":
    return new_sentence_template(...)
```

C’est ce critère qui doit guider tout le refactor.
