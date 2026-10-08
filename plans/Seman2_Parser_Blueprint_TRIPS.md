# Seman2 — Blueprint du parser linguistique symbolique
## Remplacement moderne de TRIPS/Cogent

**Statut :** Blueprint d’architecture v1  
**Objectif :** construire un moteur linguistique symbolique moderne, rapide, générique et révisable, capable de produire une analyse syntaxique et sémantique riche ainsi qu’une mémoire discursive avec coréférence, afin que le langage puisse servir de système de perception à Seman2.

---

# 1. Principe général

Le but n’est **pas** de réécrire TRIPS ligne par ligne.

Le but est de :

1. analyser les bonnes idées linguistiques de TRIPS ;
2. conserver sa couverture grammaticale et ses mécanismes utiles ;
3. supprimer son architecture historique, son plumbing, ses dépendances de dialogue spécifiques et ses coûts inutiles ;
4. réimplémenter les fonctions nécessaires avec un runtime générique, moderne et fortement indexé ;
5. utiliser TRIPS comme **oracle de régression**, corpus d’exemples et catalogue de phénomènes.

Principe fondamental :

> **On copie la couverture linguistique et les bonnes idées formelles de TRIPS, pas son architecture logicielle.**

---

# 2. Règles constitutionnelles de Seman2

## 2.1 Knowledge is data

Le runtime doit être abstrait et générique.

Les concepts linguistiques, constructions, rôles, types sémantiques, frames et règles doivent être représentés sous forme de données.

Ajouter :

- un nouveau verbe ;
- un nouveau concept ;
- une nouvelle construction ;
- un nouveau rôle ;
- un nouveau ton ;
- une nouvelle relation ;

ne doit normalement **pas nécessiter une modification du code du moteur**.

## 2.2 Les exemples ne sont pas des classes

Les noms employés dans la documentation sont des illustrations.

**NOUNS IN ARCHITECTURE EXAMPLES ARE NOT SOFTWARE CLASSES.**

Ainsi :

```text
REQUEST
TRANSFER
AGENT
OBJECT
RECIPIENT
EVENT
PERSON
```

ne doivent pas devenir automatiquement :

```text
Request
TransferEvent
AgentHandler
ObjectType
RecipientResolver
```

## 2.3 Interdictions architecturales

À éviter :

```python
if semantic_type == "REQUEST":
    ...
```

ou :

```python
def understand_request(...):
    ...
```

ou :

```python
class TransferEvent:
    ...
```

ou :

```python
if verb == "give":
    ...
```

Le runtime doit principalement fournir des opérations génériques :

```text
INDEX
MATCH
UNIFY
EXPAND
PACK
SCORE
COMPOSE
LINK
RETRIEVE
RERANK
REVISE
```

Les règles apprises et linguistiques sont des données.

---

# 3. Architecture globale

```text
PARAGRAPHE / DOCUMENT
        │
        ▼
[1] SEGMENTATION + LATTICE LEXICAL
        │
        ▼
[2] LEXIQUE / MORPHOLOGIE / FRAMES
        │
        ▼
[3] FEATURE STRUCTURES + TYPE DAG
        │
        ▼
[4] WEIGHTED CHART PARSER
        │
        ├────────────► FORÊT SYNTAXIQUE RICHE
        │
        ▼
[5] COMPOSITION SÉMANTIQUE
        │
        ▼
[6] NORMALISATION LINGUISTIQUE
        │
        ▼
[7] MÉMOIRE DISCURSIVE + CORÉFÉRENCE
        │
        ▼
[8] HYPOTHÈSES PERCEPTIVES SEMAN2
```

Le parsing reste local à la phrase.

Le contexte discursif reste global au paragraphe, au document ou à la session.

Le système idéal est donc :

> **parse local, contexte global persistant.**

---

# 4. Bloc 1 — Segmentation et lattice lexical

## 4.1 Objectif

Transformer le texte brut en spans linguistiques candidats sans prendre prématurément des décisions irréversibles.

Exemple :

```text
John's going to New York.
```

Le lattice peut conserver :

```text
John
's → possessif | is | has
going
to
New York → unité multiword possible
```

## 4.2 Structure minimale d’un candidat lexical

```text
LexicalCandidate
    span_start
    span_end
    surface
    lemma
    POS candidates
    morphology
    normalized form
    lexical source
    score
    provenance
```

## 4.3 Principes

Le système doit supporter :

- offsets caractères stables ;
- tokens ;
- ponctuation ;
- contractions ;
- multiwords ;
- formes fléchies ;
- variantes orthographiques ;
- phrases ;
- paragraphes ;
- noms propres ;
- nombres ;
- dates ;
- unités ;
- symboles.

Aucune hypothèse n’est détruite avant que les blocs suivants ne la départagent.

---

# 5. Bloc 2 — Lexique riche

Le lexique est une des pièces les plus importantes du système.

TRIPS montre qu’un lexique utile doit contenir beaucoup plus que :

```text
open = verb
```

Une entrée doit pouvoir contenir :

```text
lemma
POS
morphology
sense
semantic type
syntactic frames
semantic-role mapping
selectional restrictions
optional arguments
preferences
external lexical mappings
```

## 5.1 Exemple conceptuel

```text
tell

sense A:
    POS: verb

    frame:
        subject NP    → AGENT
        object NP     → ADDRESSEE
        complement CP → FORMAL
```

Le runtime ne possède aucun code spécial pour `tell`.

Il lit un frame.

## 5.2 Frames à supporter

Le système doit couvrir au minimum :

```text
intransitive
transitive
ditransitive

NP complement
PP complement
CP complement

subject control
object control

unaccusative
passive

expletive subject

optional argument
required argument

particle
phrasal verb

resultative
```

## 5.3 Ressources possibles

Le lexique pourra agréger :

```text
TRIPS lexical patterns
WordNet
VerbNet
FrameNet
PropBank
morphological rules
learned Seman2 lexical evidence
```

Le format interne doit rester indépendant de la source.

---

# 6. Bloc 3 — Feature structures

TRIPS utilise massivement les feature structures.

Ce principe doit être conservé.

Une unité syntaxique peut ressembler à :

```text
category = NP

features:
    number = singular
    person = 3
    case = nominative
    wh = false
    semantic_type = PERSON
```

## 6.1 Features majeures à supporter

L’analyse de TRIPS révèle notamment :

```text
AGR
NUMBER
PERSON
CASE

GAP
WH
WH-VAR

SORT
STATUS
MASS

VFORM
TENSE
ASPECT
TMA

AUX
MODAL
NEGATION

SUBCAT
SUBJ
OBJ
IOBJ
COMP

EXPLETIVE
GERUND
PARTICIPLE

COMPARATIVE
SUPERLATIVE

CTYPE
STYPE

PRO
PROFORM
REFLEXIVE

POSS
QUANTIFIER
```

Cette liste pourra évoluer, mais le moteur ne doit pas être couplé à une liste rigide.

---

# 7. Bloc 4 — Type DAG / ontologie linguistique

L’ontologie linguistique ne doit pas être confondue avec la cognition de Seman2.

Elle sert à contraindre le parsing.

Exemple :

```text
PERSON
  <: PHYSICAL_OBJECT
      <: REFERENTIAL
```

ou :

```text
EVENT
  <: SITUATION
```

## 7.1 Utilité

Le type DAG sert à :

- vérifier la compatibilité d’un rôle ;
- éliminer certaines analyses impossibles ;
- scorer des analyses plausibles ;
- généraliser des sens lexicaux ;
- contraindre la coréférence.

## 7.2 Exemple

```text
AGENT requires:
    PERSON | ORGANIZATION | PHYSICAL_OBJECT | SITUATION ...

AFFECTED requires:
    compatible referential entity
```

Le but n’est pas de dire ce qu’est réellement le monde.

Le but est de fournir une **ontologie linguistique de contraintes**.

## 7.3 Implémentation recommandée

Les types doivent être :

```text
interned IDs
```

La hiérarchie peut être précompilée sous forme de :

```text
bitsets
ancestor masks
descendant masks
```

Ainsi :

```text
is_subtype(A, B)
```

doit être presque constant-time.

---

# 8. Bloc 5 — Unification

L’unification est le cœur abstrait du système.

Une règle peut dire :

```text
NP[number=?n] + VP[number=?n]
    → CLAUSE
```

Les deux unités ne peuvent se combiner que si leurs features sont compatibles.

Même mécanisme pour :

```text
WH
GAP
CASE
TENSE
SEMANTIC TYPE
SUBCAT
```

## 8.1 Propriétés requises

L’unification doit être :

- générique ;
- rapide ;
- partiellement persistante ;
- non destructive ou rollback-safe ;
- facilement testable ;
- capable de variables ;
- capable de sous-typage ;
- capable de valeurs disjonctives ;
- capable de valeurs non spécifiées.

---

# 9. Bloc 6 — Grammaire déclarative

Les phénomènes grammaticaux ne doivent pas être encodés comme une cascade de fonctions spécialisées.

Une construction doit être une donnée.

Exemple :

```text
RULE:
    NP[number=?n]
    VP[number=?n]

→ CLAUSE

SEM:
    bind NP.ref to VP.subject-role
```

## 9.1 Une règle peut contenir

```text
RHS pattern
LHS output
feature constraints
variable bindings
semantic composition
score / prior
provenance
```

---

# 10. Bloc 7 — Weighted chart parser

L’idée du chart parser de TRIPS reste excellente.

La réimplémentation doit cependant être moderne.

Pipeline :

```text
lexical candidate
      ↓
chart
      ↓
retrieve compatible rules
      ↓
unify
      ↓
produce constituent
      ↓
pack
      ↓
agenda
```

## 10.1 Implémentation recommandée

Le cœur pourrait être écrit en Rust.

Structures recommandées :

```text
interned symbols
arena allocation
packed feature structures
rule indexes
priority queue
packed forest
bitsets
small vectors
compact IDs
```

Python peut rester utilisé pour :

- tooling ;
- inspection ;
- génération de tests ;
- conversion de ressources ;
- analyses offline.

## 10.2 Indexation

On ne doit jamais faire :

```text
new constituent
×
all grammar rules
```

Les règles peuvent être indexées selon :

```text
category
head category
vform
wh
gap
subcat class
first RHS symbol
semantic type when useful
```

---

# 11. Bloc 8 — Packed parse forest

L’ambiguïté ne doit pas causer une explosion par duplication.

Exemple :

```text
I saw the man with the telescope.
```

Deux analyses :

```text
WITH → SEE
WITH → MAN
```

La partie commune doit être stockée une seule fois.

```text
                  ┌─ WITH → SEE
shared structure ─┤
                  └─ WITH → MAN
```

## 11.1 But

Conserver :

- plusieurs analyses ;
- leur score ;
- leur provenance ;
- les sous-structures partagées.

Une phrase future peut modifier leur classement.

---

# 12. Bloc 9 — Composition sémantique

La composition sémantique doit se produire pendant le parsing.

On ne veut pas :

```text
syntax parse
   ↓
second semantic parser
```

Les règles grammaticales et lexicales doivent transporter leur contribution sémantique.

## 12.1 Exemple

```text
John opened the box.
```

doit produire :

```text
EVENT e1
type = OPEN

AGENT(e1, x1)
AFFECTED(e1, x2)

x1 = John
x2 = box
```

tout en gardant les structures syntaxiques qui ont produit ces relations.

---

# 13. Deux projections liées

Pour Seman2, il faut conserver simultanément :

```text
STRUCTURE LINGUISTIQUE
        ↕
ALIGNEMENTS
        ↕
GRAPHE SÉMANTIQUE
```

Exemple :

```text
surface:
"it"

linguistic node:
PRONOUN[3SG, neuter]

coreference:
→ Entity E42

semantic world:
E42 = BOX
```

Les deux projections restent accessibles.

---

# 14. Bloc 10 — Tense / modality / aspect / negation

Il faut conserver les informations linguistiques avant toute interprétation cognitive forte.

Exemple :

```text
He might not have left.
```

Sortie :

```text
LEAVE(e)

agent(e, x)

modal = possibility
negation = true
perfect = true
tense = ...
```

Ne pas convertir immédiatement cela en :

```text
TRUE
FALSE
IMPOSSIBLE
REQUIRED
```

La représentation doit rester suffisamment primitive pour que Seman2 apprenne ses propres abstractions.

---

# 15. Bloc 11 — Relations inter-clausales

Constructions à préserver explicitement :

```text
if
because
although
before
after
while
unless
when
since
so that
```

Exemple :

```text
John left because Mary arrived.
```

Sortie :

```text
LEAVE(e1)
ARRIVE(e2)

CAUSE/REASON(e1, e2)
```

sans coder une logique cognitive spécifique dans le parser.

---

# 16. Bloc 12 — Mémoire discursive

Chaque phrase produit des mentions.

Ces mentions peuvent pointer vers des entités discursives persistantes.

Exemple :

```text
John found a box.
He opened it.
```

Mémoire :

```text
E1 = John

mentions:
    M1 "John"
    M3 "He"

E2 = box

mentions:
    M2 "a box"
    M4 "it"
```

## 16.1 Structure possible

```text
DiscourseEntity
    entity_id
    semantic hypotheses
    type hypotheses
    salience
    last_seen
    discourse status
    mentions[]
```

---

# 17. Bloc 13 — Coréférence

Le resolver doit produire des hypothèses.

Pipeline :

```text
mention
    ↓
candidate generation
    ↓
syntactic constraints
    ↓
number / person / type
    ↓
accessibility
    ↓
semantic compatibility
    ↓
recency
    ↓
salience / focus
    ↓
ranked hypotheses
```

## 17.1 Exemple

```text
it
```

Candidats :

```text
E42 box       .91
E27 building  .23
E12 event     .09
```

La décision peut rester révisable.

---

# 18. Types de coréférence à supporter

TRIPS fournit déjà une excellente checklist.

Le nouveau système doit couvrir :

```text
he / him
she / her
it
they / them

this / that
these / those

reflexives
relative pronouns

definite descriptions
proper names

sets
sequences

temporal references
spatial references

event anaphora
proposition anaphora
```

---

# 19. Limitations explicites observées dans TRIPS à corriger

TRIPS contient des limitations explicites autour de :

```text
sets
sequences
times
spatial entities
complex definite descriptions
```

Notre système devra aller plus loin.

Exemple :

```text
John lost his job.
This devastated him.
```

`this` peut référer à :

```text
the whole previous event
```

et non à un objet physique.

---

# 20. Descriptions définies complexes

Le resolver doit supporter :

```text
the dog
the dog near Mary
the man who called yesterday
the second box on the left
the car John bought
```

Cela nécessite :

```text
entity retrieval
+
semantic/type filtering
+
descriptive constraint matching
```

---

# 21. La perception Seman2

La coréférence doit rejoindre la perception conceptuelle.

Exemple :

```text
John picked up the box.
He opened it.
```

Analyse :

```text
PICK_UP(e1)
AGENT(e1, E1)
AFFECTED(e1, E2)

OPEN(e2)
AGENT(e2, E1)
AFFECTED(e2, E2)
```

Liens linguistiques conservés :

```text
"He" → E1
"it" → E2
```

Donc Seman2 perçoit bien :

```text
same John
same box
```

et non quatre objets indépendants.

---

# 22. Couverture grammaticale minimale

La grammaire doit être validée par familles de phénomènes.

## 22.1 Noun phrases

```text
definite
indefinite
bare noun
plural
mass noun
proper noun
```

## 22.2 Determiners / quantification

```text
a
the
some
all
every
each
no
many
few

cardinality
quantifiers
measure phrases
units
partitives
```

## 22.3 Possession

```text
John's car
his car
his own car
the roof of the house
```

## 22.4 Pronouns

```text
personal
demonstrative
interrogative
relative
reflexive
reciprocal
possessive
```

## 22.5 Adjectives

```text
attributive
predicative
postpositive
adjective complements
gradable adjectives
```

## 22.6 Comparison

```text
comparative
superlative
than
as ... as
degree modifiers
scales
```

## 22.7 Verb valency

```text
intransitive
transitive
ditransitive

NP complement
PP complement
CP complement
```

## 22.8 Control

Important : TRIPS possède un très grand nombre de templates de control.

À couvrir :

```text
subject control
object control
```

Exemples :

```text
John wants to leave.
John persuaded Mary to leave.
```

## 22.9 Raising

À tester explicitement :

```text
John seems to be tired.
There appears to be a problem.
```

Même si TRIPS ne doit pas être considéré comme oracle parfait sur ce phénomène.

## 22.10 Infinitives

```text
to leave
to have left
to be taken
for John to leave
```

## 22.11 Gerunds

```text
Walking is good.
John stopped walking.
By walking home...
```

## 22.12 Participles

```text
the broken box
the man standing there
```

## 22.13 Auxiliaries

```text
be
have
do
will
can
should
might
```

## 22.14 Passive

```text
The box was opened.
The box was opened by John.
Mary was given the book.
```

## 22.15 Relative clauses

```text
the man who left
the box that John opened
the man whose dog barked
the city in which I live
```

## 22.16 Reduced relatives

```text
the device placed there
the man standing outside
```

## 22.17 Long-distance dependencies / gaps

```text
Who did John see?
Who did John talk to?
Which city did he come from?
```

## 22.18 Questions

```text
WH questions
yes/no questions
tag questions
fragment questions
embedded questions
```

## 22.19 Imperatives

```text
Open the door.
Don't open the door.
```

## 22.20 Coordination

```text
NP coordination
VP coordination
PP coordination
clause coordination
```

Exemples :

```text
John and Mary left.
John ran and jumped.
John left but Mary stayed.
```

## 22.21 Embedded clauses

```text
that clauses
if clauses
whether clauses
infinitival clauses
```

## 22.22 Conditionals

```text
if
if ... then
unless
even if
```

## 22.23 Adverbials

```text
pre-VP
post-VP
PP
manner
location
time
discourse adverbials
```

## 22.24 Resultatives

```text
wipe the table clean
freeze solid
sweep the dust into the corner
```

## 22.25 Phrasal verbs and particles

```text
pick up
turn off
look up
```

Le système doit distinguer :

```text
semantic particle
syntactic particle
preposition
```

## 22.26 Expletives

```text
It is raining.
There is a problem.
It seems that...
```

## 22.27 Fragments

```text
Which train?
Not red.
In the room.
Never in the morning.
Why not?
```

## 22.28 Apposition

```text
John, my brother, left.
Paris, the capital of France, ...
```

## 22.29 Temporal expressions

Très forte couverture souhaitée :

```text
times
dates
durations
intervals
frequencies
ranges
relative dates
time of day
day of week
month
year
age
```

## 22.30 Nominalizations

Exemples :

```text
destruction of the city
John's arrival
the driver of the truck
```

Il faut pouvoir relier les rôles nominaux aux rôles verbaux.

---

# 23. Phénomènes supplémentaires à couvrir même si TRIPS n'est pas suffisant

TRIPS n’est pas la définition de l’anglais.

Le nouveau moteur doit également avoir des tests pour :

```text
clefts
extraposition
VP ellipsis
gapping
cataphora
split antecedents
bridging reference
event anaphora
proposition anaphora
quantifier scope ambiguity
negation scope
modal scope
```

---

# 24. Ambiguïté et révision

Le parser ne doit pas considérer sa meilleure hypothèse comme une vérité.

Exemple :

```text
I saw the man with the telescope.
```

On conserve :

```text
H1:
WITH(telescope, SEE)

H2:
WITH(telescope, MAN)
```

Puis :

```text
later evidence
→ rerank H1/H2
```

---

# 25. Provenance

Rien ne doit être perdu.

Pour chaque information dérivée, conserver autant que possible :

```text
source span
source lexical candidate
source grammar rule
source semantic composition
source reference decision
score
alternative hypotheses
parser version
grammar version
lexicon version
```

---

# 26. Nothing is thrown away

Principe fondamental de Seman2 :

```text
raw text
tokens
lexical candidates
parse alternatives
semantic alternatives
reference alternatives
provenance
```

doivent rester disponibles.

Une abstraction supérieure ne remplace jamais définitivement sa preuve.

---

# 27. Structures runtime génériques

Le runtime peut se limiter à quelques familles de structures techniques.

Par exemple :

```text
Token / LexicalCandidate

FeatureStructure

GrammarRule

ParseNode
PackedAlternative

SemanticNode
SemanticRelation

Mention
DiscourseEntity
```

Ces structures sont des contenants techniques génériques.

Elles ne doivent pas devenir une taxonomie codée du monde.

---

# 28. Format conceptuel des règles

Exemple générique :

```yaml
rule:
  id: clause_np_vp

  rhs:
    - category: NP
      bind:
        number: ?n
        referent: ?subject

    - category: VP
      bind:
        number: ?n
        subject_slot: ?role
        event: ?event

  lhs:
    category: CLAUSE

  semantic:
    - link:
        predicate: ?role
        source: ?event
        target: ?subject
```

Le format réel reste à choisir.

Le point important est :

> la règle décrit le comportement, le runtime l'exécute.

---

# 29. Performance

Le système est destiné à pouvoir analyser des millions de phrases.

Il faut donc éviter toute architecture reposant sur :

```text
full scan of rules
full scan of discourse mentions
tree duplication
dynamic string comparisons everywhere
global mutable Lisp-like state
expensive serialization between internal stages
```

## 29.1 Stratégies de performance

```text
persistent process

interned IDs

precompiled grammar indexes

type bitsets

packed forest

arena allocation

compact feature maps

memoized safe operations

bounded beam

per-phrase hard budgets

document-level batching

cache of lexical/morphological lookup
```

---

# 30. Mémoire discursive efficace

La coréférence ne doit pas tester chaque mention contre tout l’historique.

Utiliser :

```text
recent mentions
+
active discourse entities
+
semantic-type indexes
+
number/person indexes
+
salience indexes
```

Exemple :

```text
"it"

candidate pool:
    recent singular non-person entities
```

avant scoring détaillé.

---

# 31. Cache

Le nouveau parser doit distinguer :

```text
lexical cache
morphological cache
rule candidate cache
type compatibility cache
feature-unification cache when safe
document/entity retrieval cache
full sentence cache when context-independent
```

Les caches dépendants du discours doivent inclure le contexte pertinent dans leur clé.

---

# 32. Tests

Le projet ne doit pas être testé uniquement avec quelques exemples humains.

Chaque phénomène linguistique doit disposer de :

```text
positive examples
negative examples
minimal pairs
ambiguous examples
adversarial examples
lexical variations
syntactic variations
```

---

# 33. Génération automatique de tests avec LLM

Pour chaque phénomène :

```text
passive
relative clause
object control
...
```

un agent LLM peut produire :

```text
1000+ examples
minimal pairs
rare constructions
counterexamples
ambiguity cases
```

Ces exemples servent à tester le moteur symbolique.

Le LLM aide à construire et valider le système.

Le LLM n’est pas le moteur runtime.

---

# 34. TRIPS comme oracle

Pipeline de développement :

```text
test corpus
   │
   ├────► TRIPS
   │        ↓
   │      LF / syntax
   │
   └────► Seman2 parser
            ↓
         syntax / semantics
```

Comparer :

```text
coverage
structure
roles
ambiguities
coreference
runtime
memory
```

Une divergence n’implique pas automatiquement que TRIPS a raison.

Elle déclenche une inspection.

---

# 35. Autres oracles possibles

Le moteur peut aussi être comparé à :

```text
ERG / ACE
Universal Dependencies
VerbNet
PropBank
FrameNet
WordNet
human test suites
LLM-generated adjudication cases
```

Aucun oracle unique ne définit la vérité.

---

# 36. Pipeline de développement recommandé

## Phase 1 — Core symbolic engine

Construire :

```text
symbol interning
feature structures
type DAG
unification
grammar rules
```

Objectif :

```text
tens of thousands of unit tests
```

avant d’ajouter la grammaire anglaise complète.

## Phase 2 — Lexical/frame layer

Définir :

```text
lexical entry schema
morphology
sense representation
argument frames
role mapping
selectional restrictions
```

Puis importer progressivement les ressources.

## Phase 3 — Chart parser

Construire :

```text
chart
agenda
rule indexes
packed forest
beam
hard budgets
```

D’abord sur une petite grammaire.

## Phase 4 — Semantic composition

Ajouter :

```text
event nodes
entity nodes
semantic relations
syntax↔semantics alignments
```

## Phase 5 — English coverage

Ajouter progressivement :

```text
NP
VP
clauses
questions
passives
control
relative clauses
gaps
TMA
coordination
...
```

## Phase 6 — Discourse

Ajouter :

```text
mentions
entities
salience
reference candidates
coreference ranking
event anaphora
```

## Phase 7 — Massive conformance suite

Tester :

```text
TRIPS
Seman2 parser
other references
```

sur des dizaines ou centaines de milliers de constructions.

## Phase 8 — Intégration Seman2

Une fois stable :

```text
syntax
+
semantics
+
reference
+
provenance
```

alimentent le niveau d’induction structurelle de Seman2.

---

# 37. Interface avec le niveau d’apprentissage Seman2

Le parser ne doit pas apprendre les concepts finaux.

Il doit fournir les matériaux.

```text
surface text
        │
        ▼
syntax structure
        │
        ▼
semantic graph
        │
        ▼
resolved discourse entities
        │
        ▼
Seman2 structural induction
```

Puis :

```text
repeated alignment
→ recurring structure
→ abstraction
→ reusable construction
```

---

# 38. Génération future

À terme, les mêmes structures doivent pouvoir être utilisées en sens inverse.

```text
semantic target
+
discourse context
+
style/context constraints
        ↓
retrieve compatible constructions
        ↓
instantiate frames
        ↓
surface realization
```

Le parser et le générateur doivent donc partager autant que possible :

```text
lexicon
frames
feature structures
construction rules
syntax↔semantic mappings
```

---

# 39. Dialogue

Le CPS de TRIPS ne doit pas devenir notre architecture de dialogue.

Il repose fortement sur :

```text
states
transitions
speech-act handlers
active goals
domain-specific behavior
```

Ce modèle est trop programmé pour Seman2.

Ce qu’on garde comme phénomènes :

```text
proposal
acceptance
rejection
correction
question
answer
repair
abandonment
confirmation
goal shift
```

Mais ils doivent être appris ou représentés comme données, pas comme handlers codés.

---

# 40. Critères de réussite du parser

On ne juge pas uniquement :

```text
"phrase parsed: yes/no"
```

Les métriques doivent inclure :

```text
coverage

syntactic structure accuracy

semantic-role accuracy

coreference accuracy

ambiguity preservation

provenance completeness

runtime

memory usage

failure behavior
```

---

# 41. Exemple de test canonique

Input :

```text
John gave Mary the box because she asked him for it.
```

Sortie attendue conceptuelle :

```text
SYNTAX

main clause
    subject: John
    predicate: gave
    recipient: Mary
    object: the box

subordinate causal clause
    subject: she
    predicate: asked
    object: him
    complement: for it
```

Sémantique :

```text
GIVE(e1)
AGENT(e1, E1)
RECIPIENT(e1, E2)
THEME(e1, E3)

ASK(e2)
AGENT(e2, E2)
ADDRESSEE(e2, E1)
THEME(e2, E3)

REASON(e1, e2)
```

Coréférence :

```text
she → Mary
him → John
it → box
```

Provenance :

```text
John → span(...)
Mary → span(...)
box → span(...)
she → span(...)
him → span(...)
it → span(...)
```

Ce genre de phrase doit devenir un test d’intégration standard.

---

# 42. Principe de conception final

Le nouveau moteur doit rester conceptuellement petit.

Sa puissance doit venir :

```text
des règles
des données
des frames
des contraintes
des alignements
des index
```

et non d’une accumulation de logique spécialisée.

Le runtime doit essentiellement savoir :

```text
MATCH
UNIFY
EXPAND
PACK
SCORE
COMPOSE
LINK
RETRIEVE
RERANK
REVISE
```

Si l’ajout d’un phénomène linguistique exige régulièrement d’ajouter :

```text
if phenomenon == X:
```

le design dérive dans la mauvaise direction.

---

# 43. Résumé architectural

Le parser Seman2 doit être :

```text
symbolique
data-driven
feature-based
typed
ambiguity-preserving
incremental
context-aware
coreference-aware
fast
compact
revisable
provenance-preserving
```

TRIPS devient :

```text
legacy implementation
        ↓
linguistic archaeology
        ↓
capability checklist
        ↓
test oracle
        ↓
modern Seman2 parser
```

Le but final n’est donc pas de construire un nouveau TRIPS.

Le but est de construire :

> **un moteur linguistique symbolique moderne suffisamment riche pour servir de système de perception à Seman2, tout en restant assez générique pour que le reste de l’intelligence puisse être appris plutôt que programmé.**
