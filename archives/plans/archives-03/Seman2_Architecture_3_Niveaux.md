# Seman2 — Architecture nouvelle en 3 niveaux
## Référence architecturale — vNext

> **Statut : architecture de référence pour le nouveau cœur de Seman2**
>
> **Objectif principal :** construire un système cognitif symbolique qui ingère continuellement du langage naturel, conserve toute l’évidence utile, exploite une analyse linguistique profonde existante, apprend des représentations sémantiques et des constructions linguistiques de plus en plus abstraites, puis réutilise ces connaissances pour comprendre et générer du langage — **sans encoder en dur les concepts du monde, les actes de dialogue, les tons, les structures de phrases ou les catégories sémantiques découvertes.**
>
> **Principe directeur :** Seman2 n’est pas une collection de handlers spécialisés. Seman2 est un **moteur générique d’acquisition, d’alignement, d’abstraction, de révision et de réutilisation de structures**.

---

# 0. Résumé exécutif

La nouvelle architecture Seman2 est volontairement réduite à **trois niveaux** :

1. **Niveau 1 — Flux d’évidence**
   - ingère continuellement le texte et le contexte observable ;
   - conserve l’original, l’ordre, la provenance, le locuteur et les relations de contexte ;
   - ne tente pas de « comprendre » ;
   - rend tout rejouable et réinterprétable.

2. **Niveau 2 — Interprétation linguistique profonde**
   - utilise **TRIPS** comme analyseur linguistique principal ;
   - produit simultanément deux projections issues de la même analyse :
     - **branche sémantique** : objets évoqués, événements, rôles, relations, temps, aspect, modalités, références, etc. ;
     - **branche structurale** : arbre/structure grammaticale, relations syntaxiques, morphologie, ordre, fragments et coquilles de constructions ;
   - conserve les ambiguïtés, les hypothèses et les liens vers le texte original ;
   - peut réviser une interprétation à la lumière du contexte discursif.

3. **Niveau 3 — Modèle appris couplé**
   - stocke les structures apprises dans un substrat générique de graphes ;
   - apprend des fragments structuraux via **Data-Oriented Parsing (DOP)** avec **disco-dop** ;
   - aligne les structures linguistiques aux structures sémantiques ;
   - généralise les observations en motifs, schémas et concepts progressivement plus abstraits ;
   - apprend les propriétés discursives, pragmatiques, stylistiques et de ton comme **distributions d’usage attachées aux structures**, et non comme classes codées en dur ;
   - sert dans les deux directions :
     - **compréhension** : surface → structures → sens ;
     - **génération** : sens + contexte → structures apprises → surface.

La stack choisie est :

| Fonction | Technologie choisie | Rôle |
|---|---|---|
| Orchestration Seman2 | **Python** | colle minimale, ingestion, adapters, tests, orchestration |
| Analyse linguistique runtime | **TRIPS NLU / TRIPS semantic parser** | analyse profonde syntaxique + sémantique + ontologique + contexte |
| Induction de fragments structurels | **DOP / disco-dop** | extraction/réutilisation probabiliste de fragments de structure |
| Graphe générique de connaissances | **OpenCog AtomSpace** | stockage et interrogation de structures symboliques génériques |
| Pattern mining générique | **OpenCog Miner** | découverte de motifs récurrents dans les graphes |
| Oracle grammatical secondaire | **ERG + ACE + PyDelphin** | validation hors runtime des distinctions grammaticales |
| Journal d’évidence brut | **SQLite en mode WAL** au départ | log append-only simple, portable, rejouable |

**Important :** ERG/ACE n’est pas un deuxième pipeline runtime. Il sert d’**oracle grammatical de validation** et de comparaison pour les tests difficiles.  
**Important :** AtomSpace n’impose aucune ontologie métier à Seman2. Il sert comme **substrat de graphes et de requêtes**, pas comme cerveau conceptuel pré-écrit.

---

# 1. Constitution de Seman2

Cette section est normative.

Toute implémentation, tout agent de programmation et toute future évolution de l’architecture doivent respecter ces invariants.

## 1.1 Knowledge is data

Toute connaissance du langage, du monde, du discours ou du comportement conversationnel doit être représentée comme **donnée**.

Cela inclut notamment :

- concepts ;
- relations ;
- rôles ;
- constructions linguistiques ;
- structures de phrases ;
- régularités grammaticales apprises ;
- schémas d’événements ;
- catégories discursives ;
- actes de dialogue ;
- registres ;
- niveaux de politesse ;
- styles ;
- tons ;
- corrélations temporelles ;
- patrons de référence ;
- associations forme ↔ sens.

Le runtime ne doit pas contenir de code métier équivalent à :

```python
if concept == "REQUEST":
    ...
```

ou :

```python
class TransferEvent:
    ...
```

ou :

```python
def understand_passive_sentence(...):
    ...
```

Ces choses peuvent **émerger comme structures de données**, mais ne doivent pas devenir des primitives architecturales sans justification explicite.

---

## 1.2 Les exemples ne sont jamais des spécifications

Une notation telle que :

```text
S₁(
    R₁ = X,
    R₂ = Y,
    SUB = S₂(...)
)
```

est une illustration de structure.

Si la documentation utilise occasionnellement un exemple humain tel que :

```text
REQUEST(...)
```

cela **ne signifie pas** qu’il faut créer :

- `Request` ;
- `RequestHandler` ;
- `SpeechAct.REQUEST` ;
- une table `requests` ;
- une méthode `handle_request()` ;
- un module `request.py`.

### Règle obligatoire pour les agents

> **Tout nom sémantique lisible par un humain présent dans un exemple est présumé illustratif et NON architectural, sauf si le document indique explicitement `RUNTIME PRIMITIVE`.**

---

## 1.3 Le runtime ne dispatch pas sur la sémantique humaine

Le runtime peut dispatch sur :

- un type d’objet technique ;
- une opération d’infrastructure ;
- une classe de structure générique ;
- une stratégie algorithmique explicitement définie.

Il ne doit pas dispatch sur :

- « question » ;
- « requête » ;
- « transfert » ;
- « possession » ;
- « chien » ;
- « sarcasme » ;
- « joie » ;
- « politesse » ;
- « passif » ;

si ces catégories sont censées être des connaissances apprises ou importées.

Le moteur doit plutôt savoir effectuer des opérations génériques telles que :

```text
MATCH
ALIGN
GENERALIZE
SPECIALIZE
MERGE
SPLIT
INSTANTIATE
REWRITE
RANK
RETRIEVE
ASSOCIATE
COMPARE
REVISE
INVALIDATE
```

---

## 1.4 Apprendre ne doit pas exiger de modifier le code

Test constitutionnel :

> **Si Seman2 apprend une nouvelle construction, un nouveau concept, une nouvelle relation, un nouveau rôle discursif ou une nouvelle régularité de ton, aucun fichier source du runtime ne devrait devoir être modifié.**

Une connaissance nouvellement acquise doit produire :

- de nouveaux nœuds ;
- de nouvelles relations ;
- de nouveaux fragments ;
- de nouveaux alignements ;
- de nouvelles distributions ;
- de nouveaux scores ;
- de nouvelles hypothèses ;

mais pas de nouvelles classes métier.

---

## 1.5 Rien d’interprétatif n’est irréversible

Le texte brut est une observation.

Une analyse est une hypothèse.

Une généralisation est une hypothèse.

Un concept appris est une abstraction.

Une règle induite est un modèle.

Aucune de ces sorties ne doit être confondue avec l’évidence originale.

Chaque structure dérivée doit pouvoir répondre à :

```text
D’où viens-tu ?
Quelles observations te supportent ?
Quel analyseur t’a produite ?
À quelle version ?
Avec quel score ?
Quelles hypothèses alternatives existaient ?
Quelles connaissances dérivent de toi ?
```

---

## 1.6 Une interprétation peut rester ambiguë

Seman2 ne doit pas forcer artificiellement une décision.

Une observation peut produire :

```text
Hypothèse A : 0.54
Hypothèse B : 0.37
Hypothèse C : 0.09
```

Ces hypothèses peuvent survivre.

Un nouveau tour de dialogue, une phrase ultérieure ou une nouvelle connaissance peut modifier leur poids.

Le système doit pouvoir faire de la **réinterprétation rétroactive**.

---

## 1.7 Aucune information ne doit être jetée simplement parce qu’elle ne sert pas à la représentation sémantique finale

Une phrase contient plusieurs sortes d’information :

- contenu propositionnel ;
- structure grammaticale ;
- choix lexical ;
- ordre ;
- morphologie ;
- ambiguïtés ;
- ponctuation ;
- répétitions ;
- formulation ;
- relation au contexte ;
- caractéristiques discursives ;
- indices pragmatiques ;
- traits de registre ;
- traces d’erreurs ;
- phénomènes inhabituels.

La sémantique ne remplace pas la phrase.

La structure ne remplace pas la phrase.

Le modèle abstrait ne remplace pas les observations.

---

# 2. Architecture générale

```text
┌─────────────────────────────────────────────────────────────────────┐
│ NIVEAU 1 — FLUX D'ÉVIDENCE                                         │
│                                                                     │
│ texte brut • tours • documents • locuteurs • ordre • provenance     │
│ contexte observable • versions • frontières • métadonnées           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ NIVEAU 2 — INTERPRÉTATION LINGUISTIQUE PROFONDE                    │
│                         TRIPS                                       │
│                                                                     │
│              même analyse / même provenance                         │
│                       ┌───────────┐                                 │
│                       │           │                                 │
│                       ▼           ▼                                 │
│             BRANCHE SÉMANTIQUE   BRANCHE STRUCTURALE               │
│             événements           syntaxe                            │
│             participants         dépendances                        │
│             relations            constituants                       │
│             rôles                ordre                              │
│             temps/aspect         morphologie                        │
│             modalité             fragments                          │
│             référence            coquilles                           │
│             discours             lexicalisation                     │
└───────────────────┬───────────────────────────┬─────────────────────┘
                    │                           │
                    └──────────────┬────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ NIVEAU 3 — MODÈLE APPRIS COUPLÉ                                    │
│                                                                     │
│ AtomSpace + Miner                DOP / disco-dop                    │
│                                                                     │
│  graphes sémantiques  ⇄  alignements  ⇄  fragments/constructions   │
│           │                                    │                    │
│           └──────── abstraction / induction ───┘                    │
│                               │                                     │
│                               ▼                                     │
│ motifs • concepts • schémas • constructions • distributions d'usage│
│                               │                                     │
│                     ⇅ compréhension/génération                      │
└─────────────────────────────────────────────────────────────────────┘
```

Il n’existe pas de quatrième couche « dialogue », « raisonnement », « ton » ou « génération ».

Ces capacités sont des **usages du modèle du niveau 3** et de ses structures apprises.

---

# 3. Niveau 1 — Flux d’évidence

## 3.1 Mission

Le niveau 1 répond à une seule question :

> **Qu’est-ce qui a été observé, dans quel ordre et dans quel contexte observable ?**

Il ne répond pas à :

> Qu’est-ce que cela signifie ?

Il ne produit aucune ontologie.

Il ne décide pas qu’une phrase est une demande.

Il ne décide pas que deux mots désignent la même chose.

Il ne crée pas de concept du monde.

---

## 3.2 Unité fondamentale : EvidenceUnit

`EvidenceUnit` est une structure technique et générique.

Exemple conceptuel :

```yaml
id: ev_000183
stream_id: conversation_42
sequence: 183
kind: text
raw: "I thought Peter had already left."
source:
  type: dialogue
  source_id: user_A
observed_at:
  relative_order: 183
context:
  previous: ev_000182
  next: null
metadata:
  language_hint: en
  channel: text
```

Les champs précis peuvent évoluer.

L’essentiel est de préserver :

- l’original ;
- l’identité ;
- l’ordre ;
- la provenance ;
- les relations de voisinage ;
- le contexte conversationnel/documentaire.

---

## 3.3 Ingestion continue

Seman2 doit être capable de recevoir :

- un corpus massif ;
- un flux ligne par ligne ;
- un livre ;
- des articles ;
- une conversation interactive ;
- une suite de conversations ;
- des événements produits par d’autres composants.

Le mécanisme conceptuel reste identique :

```text
SOURCE
  ↓
NORMALISATION NON DESTRUCTIVE
  ↓
APPEND EVIDENCE
  ↓
QUEUE D'INTERPRÉTATION
  ↓
ACK / CHECKPOINT
```

---

## 3.4 Normalisation autorisée

Le niveau 1 peut effectuer des opérations techniques non interprétatives :

- normalisation d’encodage ;
- conversion des fins de ligne ;
- détection grossière de langue ;
- segmentation candidate ;
- extraction de métadonnées ;
- contrôle d’intégrité ;
- calcul de hash ;
- attribution d’identifiants.

### Il ne doit pas

- corriger silencieusement les fautes ;
- remplacer le texte original ;
- forcer une segmentation définitive ;
- normaliser la ponctuation en perdant l’original ;
- décider du sens.

Une correction peut être proposée au niveau 2 comme **hypothèse dérivée**, jamais remplacer l’évidence.

---

## 3.5 Stockage choisi : SQLite WAL

Pour la première implémentation :

- **SQLite** ;
- mode **WAL** ;
- modèle append-only autant que possible.

Raisons :

- zéro infrastructure serveur ;
- transactionnel ;
- performant pour un prototype sérieux ;
- facilement inspectable ;
- facilement exportable ;
- rejouable ;
- migrations simples ;
- approprié comme journal de provenance.

SQLite n’est **pas** la mémoire cognitive.

Il est le **journal des observations et traitements**.

---

## 3.6 Rejeu

Tout le système doit être rejouable depuis le niveau 1.

Cas d’usage :

```text
TRIPS version N
→ 1 000 000 observations analysées

TRIPS version N+1
→ amélioration substantielle

REPLAY
→ nouvelles analyses
→ anciennes analyses conservées
→ nouvelles hypothèses
→ propagation contrôlée
```

C’est une propriété importante du système.

---

# 4. Niveau 2 — Interprétation linguistique profonde

## 4.1 Technologie principale : TRIPS

### Choix

**TRIPS NLU / semantic parser** est l’analyseur linguistique runtime retenu.

Raisons principales :

- parser linguistique profond ;
- analyse syntaxique ;
- lexique riche ;
- contraintes syntaxiques, sémantiques et ontologiques intégrées ;
- Logical Form structurée ;
- représentations d’événements et d’entités ;
- rôles sémantiques ;
- temps/aspect ;
- quantification et modalités ;
- speech acts présents dans la représentation TRIPS ;
- contexte et référence dans l’écosystème TRIPS ;
- variantes capables de parser des paragraphes ;
- usage historique dans dialogue et extraction de connaissances.

TRIPS ne devient **pas** l’architecture de Seman2.

Il devient son **instrument perceptif linguistique principal**.

---

## 4.2 Principe : une analyse, deux projections

Le résultat du niveau 2 doit toujours être considéré sous deux angles simultanés.

```text
                 ANALYSE TRIPS
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       SEMANTIC VIEW       STRUCTURAL VIEW
```

Ces deux vues conservent un lien vers :

- les mêmes spans ;
- les mêmes tokens ;
- les mêmes unités d’évidence ;
- la même hypothèse de parse ;
- la même provenance.

C’est ce couplage qui permettra l’apprentissage du niveau 3.

---

# 5. Branche sémantique

## 5.1 Ce qu’elle représente

Elle extrait les structures évoquées par l’énoncé.

Par exemple, elle peut contenir génériquement :

```text
structure S17
  relation/predicate -> P4
  participant slot R1 -> E3
  participant slot R2 -> E8
  temporal properties -> ...
  modality -> ...
  provenance -> ev_000183
```

La notation humaine peut éventuellement nous permettre de dire :

```text
« ceci ressemble à un événement »
```

mais le runtime doit conserver des structures génériques.

---

## 5.2 Types d’information utiles

Sans les figer comme architecture métier, TRIPS peut fournir ou contribuer à représenter :

- entités ;
- événements ;
- états ;
- propriétés ;
- relations ;
- participants ;
- rôles ;
- relations temporelles ;
- aspect ;
- négation ;
- modalité ;
- quantification ;
- référence ;
- coréférence ;
- parole rapportée ;
- actes discursifs ;
- connecteurs discursifs.

Tout cela est traité comme **évidence interprétative**.

---

## 5.3 La branche sémantique n’est pas « la vérité »

Une phrase :

```text
John probably left.
```

ne doit pas créer la même nature de connaissance que :

```text
John left.
```

De même :

```text
Mary said John left.
```

ne doit pas être aplati en :

```text
John left = true
```

Le graphe doit préserver :

- source ;
- embedding/context ;
- modalité ;
- attribution ;
- degré de confiance ;
- provenance.

---

## 5.4 Temps

Le temps doit rester compatible avec le principe Seman2 :

> **les relations temporelles entre événements, états, observations et contextes sont primaires ; les timestamps absolus sont des ancres externes, non la structure fondamentale du temps.**

Exemple conceptuel :

```text
S1 BEFORE S2
S3 DURING S2
S4 OVERLAPS S5
```

Une date :

```text
2026-10-06 19:00
```

est un point d’ancrage issu d’une source.

Elle ne remplace pas les relations.

---

## 5.5 Révision contextuelle

Une phrase ultérieure peut apporter de l’information sur une phrase précédente.

Exemple :

```text
E1: "The bottle was beside the glass."
E2: "It was cracked."
E3: "The glass was brand new."
```

À E2, plusieurs référents peuvent être candidats.

E3 peut modifier le classement.

Seman2 doit pouvoir conserver :

```text
interpretation(E2, H1)
interpretation(E2, H2)
```

puis :

```text
score(H1) := updated
score(H2) := updated
```

sans modifier E2.

---

# 6. Branche structurale

## 6.1 Mission

Cette branche répond à :

> **Comment cette information a-t-elle été exprimée ?**

Elle conserve :

- structure syntaxique ;
- ordre des constituants ;
- relations ;
- morphologie ;
- lexèmes ;
- réalisations ;
- alternatives ;
- fragments ;
- spans ;
- dépendances ;
- constituants.

---

## 6.2 Ne pas confondre structure et sens

Deux phrases peuvent partager beaucoup de sens et avoir des structures différentes.

Deux phrases peuvent partager une structure et avoir des sens très différents.

Seman2 ne doit donc jamais fusionner prématurément :

```text
structure linguistique
```

et :

```text
structure du monde
```

Leur relation doit être **apprise par alignement**.

---

## 6.3 Coquilles

Une « coquille » est une abstraction d’une structure observée.

Exemple humain :

```text
NP₁ V NP₂ NP₃
```

ou :

```text
NP₁ V NP₃ PREP NP₂
```

Mais le runtime ne doit pas forcément les encoder comme strings symboliques de ce genre.

Une coquille doit être une structure générique contenant :

- nœuds ;
- relations ;
- slots ;
- contraintes ;
- fragments ;
- variables ;
- statistiques ;
- provenance.

---

# 7. DOP — apprentissage structurel

## 7.1 Technologie choisie

**Data-Oriented Parsing (DOP)** avec **disco-dop** est choisi comme technologie initiale d’induction de fragments structuraux.

Le rôle de DOP est précis :

> extraire, compter et réutiliser des fragments de structures observées à plusieurs granularités.

DOP ne devient pas :

- le moteur conceptuel ;
- la sémantique ;
- la mémoire du monde ;
- le gestionnaire de dialogue.

---

## 7.2 Intuition

À partir de nombreux arbres :

```text
A
├── B
│   ├── C
│   └── D
└── E
```

DOP peut réutiliser des fragments plus petits :

```text
B(C,D)
```

ou plus grands :

```text
A(B(C,D),E)
```

Ce mécanisme permet de ne pas imposer que toute connaissance grammaticale soit :

- atomique ;
- écrite à la main ;
- limitée à une CFG minimale.

---

## 7.3 Hiérarchie émergente

Le système peut progressivement accumuler :

```text
éléments simples
      ↓
fragments récurrents
      ↓
fragments de fragments
      ↓
constructions de plus grande taille
      ↓
structures discursives récurrentes
```

La granularité n’est pas prescrite.

---

# 8. Oracle grammatical secondaire : ERG + ACE + PyDelphin

## 8.1 Pourquoi un oracle secondaire

TRIPS est choisi comme runtime parce que nous voulons :

- syntaxe ;
- sémantique ;
- ontologie ;
- contexte ;
- LF ;
- interprétation.

Cependant, pour les cas linguistiques difficiles, Seman2 doit pouvoir être testé contre une tradition grammaticale extrêmement riche.

Nous retenons donc :

- **English Resource Grammar (ERG)** ;
- **ACE** ;
- **PyDelphin**.

---

## 8.2 Rôle exact

ERG n’est pas exécuté sur chaque entrée en production.

Il sert à :

- constituer des suites de tests ;
- examiner des ambiguïtés ;
- vérifier des distinctions syntaxiques ;
- comparer les analyses TRIPS ;
- détecter une perte d’information grammaticale ;
- guider les adaptations de la branche structurale.

---

## 8.3 NO-GO

Ne pas construire :

```text
TRIPS
  +
ERG
  +
ULF
  +
AMR
  +
5 autres parsers
```

sur chaque phrase.

Le runtime principal reste simple.

---

# 9. Niveau 3 — Modèle appris couplé

## 9.1 Mission

Le niveau 3 répond à trois questions :

1. **Quelles régularités existe-t-il dans ce que nous observons ?**
2. **Quelles structures linguistiques correspondent à quelles structures sémantiques ?**
3. **Quelles abstractions plus générales permettent de compresser et prédire les observations ?**

---

## 9.2 Technologie de graphe choisie : AtomSpace

AtomSpace est retenu comme substrat générique pour représenter :

- structures ;
- relations ;
- graphes ;
- hypergraphes ;
- variables ;
- motifs ;
- statistiques ;
- liens de provenance ;
- hypothèses ;
- alignements.

### Ce qu’AtomSpace n’est pas

Il ne doit pas imposer :

- l’ontologie OpenCog complète comme vérité ;
- un modèle psychologique prédéfini ;
- OpenPsi ;
- un chatbot OpenCog ;
- des concepts métier.

Nous utilisons **la mécanique de représentation et de requête**, pas une cognition préfabriquée.

---

# 10. Trois familles de structures au niveau 3

Il est utile de distinguer conceptuellement trois familles, mais elles vivent dans **le même modèle couplé**, pas dans trois layers.

```text
SEMANTIC PATTERNS
STRUCTURAL PATTERNS
ALIGNMENTS + CONTEXT STATISTICS
```

---

## 10.1 Semantic patterns

Ils représentent des régularités observées dans les analyses sémantiques.

Au début :

```text
instance S1
instance S2
instance S3
```

Puis :

```text
pattern P1 matches S1,S2,S3
```

Puis :

```text
pattern P2 generalizes P1,P7,P9
```

La hiérarchie n’a pas besoin d’être pré-écrite.

---

## 10.2 Structural patterns

Ils proviennent principalement :

- des analyses structurelles ;
- des fragments DOP ;
- de regroupements statistiques ;
- de généralisations.

Ils peuvent représenter :

- petits fragments ;
- constructions locales ;
- constructions longues ;
- séquences de plusieurs constituants ;
- régularités de plusieurs tours de dialogue.

---

## 10.3 Alignments

Un alignement relie :

```text
partie de structure linguistique
             ↕
partie de structure sémantique
```

Exemple purement illustratif :

```text
Structural fragment C17
slot x1
slot x2
slot x3

Semantic pattern P42
role r1
role r2
role r3

Alignment A88:
x1 ↔ r1
x2 ↔ r3
x3 ↔ r2
```

Aucun de ces slots n’est « agent » ou « objet » dans le runtime.

Ces noms peuvent être attachés comme données provenant de TRIPS, mais la mécanique d’alignement reste générique.

---

# 11. Comment naît une abstraction

## 11.1 Étape 1 — observations spécifiques

Le système observe plusieurs structures.

```text
S1
S2
S3
S4
```

---

## 11.2 Étape 2 — ressemblances structurelles

Le Miner et les opérations génériques découvrent :

```text
subgraph G appears in S1,S2,S4
```

ou DOP découvre :

```text
fragment C appears in T1,T3,T9
```

---

## 11.3 Étape 3 — alignement

Le système découvre que :

```text
C
```

est régulièrement associé à :

```text
G
```

avec certaines correspondances entre slots.

---

## 11.4 Étape 4 — généralisation

Les constantes qui varient deviennent des variables.

Les éléments stables deviennent les contraintes.

On obtient :

```text
Pattern P
```

---

## 11.5 Étape 5 — abstraction d’abstraction

Des patterns peuvent eux-mêmes être comparés.

```text
P1
P2
P3
```

peuvent produire :

```text
P4
```

si P4 explique des propriétés communes.

Il n’y a aucune limite architecturale imposée au nombre de niveaux d’abstraction.

Les **trois niveaux de l’architecture ne sont pas trois niveaux de conceptualisation**.

Le niveau 3 peut contenir une profondeur arbitraire de structures apprises.

---

# 12. OpenCog Miner

## 12.1 Rôle

**OpenCog Miner** est utilisé comme outil initial pour trouver des patterns fréquents dans les graphes.

Il ne décide pas seul qu’un pattern est « un concept ».

Un pattern devient intéressant lorsqu’il présente par exemple :

- fréquence ;
- stabilité ;
- pouvoir prédictif ;
- réutilisabilité ;
- compression ;
- alignements cohérents ;
- capacité à expliquer plusieurs observations.

---

## 12.2 Importance de la compression

Une bonne abstraction doit réduire la description nécessaire.

Supposons :

```text
100 structures
```

qui partagent un motif.

Si un pattern général + 100 bindings décrit l’ensemble plus simplement que 100 descriptions indépendantes, c’est un indice d’abstraction utile.

Seman2 peut utiliser progressivement une philosophie de type :

- fréquence ;
- MDL/compression ;
- prédiction ;
- stabilité.

Les algorithmes précis peuvent évoluer sans changer l’architecture.

---

# 13. Aller-retour structure ↔ sens

C’est le cœur de la nouvelle architecture.

```text
        STRUCTURE
            │
            │ alignement
            ⇅
          SENS
```

Aucun côté n’est considéré comme subordonné à l’autre.

---

## 13.1 Compréhension

Flux :

```text
texte
 ↓
TRIPS
 ↓
structure observée
 ↓
fragments / constructions candidates
 ↓
alignements connus
 ↓
structures sémantiques candidates
 ↓
contexte
 ↓
ranking
 ↓
hypothèses interprétatives
```

TRIPS fournit déjà une sémantique riche.

Les alignements appris permettent à Seman2 de :

- renforcer ;
- spécialiser ;
- compléter ;
- comparer ;
- réinterpréter ;

cette analyse au fil de l’apprentissage.

---

## 13.2 Génération

La génération utilise les mêmes connaissances à l’envers.

```text
contenu sémantique à exprimer
 ↓
patterns compatibles
 ↓
alignements sémantique → structures
 ↓
constructions candidates
 ↓
contraintes contextuelles
 ↓
ranking
 ↓
composition
 ↓
réalisation grammaticale
```

Il ne doit pas exister :

```python
if semantic_type == X:
    return "template ..."
```

---

# 14. Discours et dialogue

## 14.1 Pas de quatrième couche

Le dialogue est simplement un cas où les EvidenceUnits sont reliées dans une séquence interactive.

```text
turn 1
turn 2
turn 3
turn 4
```

Le système peut apprendre des patterns couvrant plusieurs unités.

---

## 14.2 Structures multi-tours

Exemple abstrait :

```text
C1 occurs in turn N
C2 often occurs in turn N+1
```

avec :

```text
semantic pattern P1 at N
semantic pattern P2 at N+1
```

Le système peut apprendre :

```text
DIALOGUE_PATTERN D7
```

sans que `D7` soit codé comme :

```python
QuestionAnswerPair
```

Un humain pourrait reconnaître certains patterns comme :

- question/réponse ;
- salutation ;
- réparation ;
- clarification ;
- accusation/défense ;
- offre/acceptation ;

mais le runtime n’a pas besoin de ces catégories à l’avance.

---

# 15. Ton, style, registre et pragmatique

## 15.1 Position architecturale

Le ton n’est :

- ni une branche primaire ;
- ni une couche séparée ;
- ni un enum.

Il est une **régularité contextuelle d’usage**.

---

## 15.2 Principe

Une structure linguistique peut accumuler des statistiques de contexte.

```text
Construction C17

observed_with:
  context_cluster K2 : 0.61
  context_cluster K9 : 0.24
  context_cluster K4 : 0.15
```

Ces clusters peuvent eux-mêmes être abstraits.

---

## 15.3 Contextes possibles

Les dimensions observables peuvent inclure génériquement :

- relation entre locuteurs ;
- position dans la conversation ;
- réponse à quelle structure ;
- densité lexicale ;
- ponctuation ;
- choix lexicaux ;
- longueur ;
- répétition ;
- symétrie des tours ;
- formes de modalité ;
- degré de certitude ;
- réaction du partenaire ;
- corpus/source ;
- auteur ;
- genre textuel.

Aucune catégorie humaine fixe n’est nécessaire.

---

## 15.4 Émergence du ton

Si certaines constructions sont statistiquement associées à certains contextes et réactions, le système peut découvrir des groupes.

Un humain peut appeler un groupe :

```text
formel
```

ou :

```text
sarcastique
```

Mais cette étiquette est secondaire.

La connaissance réelle est :

```text
ensemble de structures
+
distribution de contextes
+
effets/reactions
+
associations lexicales
```

---

# 16. Questions et réponses

Seman2 ne contient pas une fonction `answer_question()` spécifique à une classe sémantique codée.

Le système reçoit une structure d’entrée.

TRIPS peut déjà produire des informations de speech act / LF.

Au niveau 3, Seman2 apprend :

```text
certaines structures d’entrée
→ déclenchent/recherchent
→ certains types de contenu
→ suivis par certaines structures de sortie
```

La résolution elle-même peut faire appel à :

- matching ;
- recherche dans le graphe ;
- inférence générique ;
- retrieval ;
- comparaison ;
- instanciation de patterns.

---

# 17. Mémoire du monde

## 17.1 Pas de duplication artificielle

Il n’est pas nécessaire de créer :

- mémoire épisodique ;
- mémoire sémantique ;
- mémoire discursive ;
- mémoire de concepts ;

comme quatre services indépendants dès le départ.

Le même graphe peut différencier les structures par leurs relations et leur provenance.

---

## 17.2 Observation vs abstraction

```text
OBSERVATION
   ↓ supports
HYPOTHESIS
   ↓ generalized_into
PATTERN
   ↓ generalized_into
ABSTRACTION
```

La provenance permet de redescendre.

---

# 18. Contradiction et révision

Une nouvelle observation ne supprime pas automatiquement l’ancienne.

Exemple abstrait :

```text
E1 supports H1
E2 supports NOT(H1)
```

Le système doit pouvoir représenter :

- contradiction ;
- source ;
- ordre ;
- fiabilité ;
- contexte.

La résolution éventuelle est un problème générique de ranking/révision.

Pas :

```python
if fact_conflict:
    delete_old_fact()
```

---

# 19. Provenance obligatoire

Chaque structure apprise importante doit pointer vers ses preuves.

Exemple :

```text
Pattern P77
  derived_from:
    E1001
    E1044
    E1098
    ...
  derivation:
    algorithm = miner_v...
    params = ...
    date = ...
```

Un changement d’algorithme peut produire :

```text
P77_v2
```

sans effacer P77.

---

# 20. Pipeline d’ingestion continue

```text
1. réception EvidenceUnit
2. append journal
3. ajout queue interprétation
4. TRIPS analyse avec contexte disponible
5. enregistrement analyses candidates
6. projection semantic view
7. projection structural view
8. insertion niveau 3
9. mise à jour DOP
10. pattern mining incrémental/batch
11. mise à jour alignements
12. mise à jour abstractions
13. révision éventuelle d’hypothèses antérieures
```

Les étapes 9–12 ne doivent pas nécessairement être exécutées après chaque phrase.

Elles peuvent fonctionner :

- incrémentalement ;
- périodiquement ;
- en micro-batches.

---

# 21. Cycles awake / consolidation

Seman2 peut profiter d’un modèle simple :

```text
INGEST
  ↓
interpret continuously
  ↓
lightweight updates
  ↓
periodic consolidation
  ↓
recompute patterns
  ↓
merge/split abstractions
  ↓
rerank
```

Ce mécanisme rappelle certains travaux OpenCog Learn, mais il reste une stratégie d’exécution, pas une nouvelle couche.

---

# 22. Reprocessing

Lorsqu’une abstraction nouvelle est créée, elle peut être appliquée aux anciennes observations.

```text
new abstraction P
      ↓
retrieve compatible old evidence
      ↓
test
      ↓
new alignments
      ↓
possible reinterpretations
```

Ainsi le système peut devenir « plus intelligent rétrospectivement ».

---

# 23. Structure minimale des données internes

Le modèle interne doit rester générique.

Une base minimale pourrait contenir les notions techniques suivantes :

```text
Evidence
Analysis
Structure
Node
Edge / Relation
Variable
Pattern
Fragment
Alignment
Hypothesis
Context
Score
Provenance
Derivation
Binding
```

Ces notions sont architecturales.

Les notions suivantes ne le sont pas :

```text
Dog
Request
Transfer
Question
Sarcasm
Possession
PassiveSentence
Promise
Anger
```

---

# 24. API conceptuelle minimale

Le nouveau cœur Seman2 devrait idéalement offrir peu d’opérations.

```text
ingest(evidence)

interpret(evidence, context)

store(structure)

match(pattern, structure)

retrieve(constraints)

align(structure_a, structure_b)

generalize(structures)

instantiate(pattern, bindings)

rank(candidates, context)

revise(hypothesis, new_evidence)

trace(structure)

generate(target_structure, context)
```

Même cette liste est conceptuelle : elle ne prescrit pas nécessairement une fonction Python par ligne.

---

# 25. NO-GO absolus

## 25.1 Pas de modèles métier codés

Interdit :

```text
RequestHandler
QuestionHandler
TransferEvent
PossessionState
SarcasmDetector
GreetingManager
```

sauf s’ils sont explicitement implémentés comme **adaptateurs externes optionnels**, jamais comme cœur cognitif.

---

## 25.2 Pas de templates de phrases codés dans le runtime

Interdit :

```python
return f"Could you {verb} {obj}?"
```

comme mécanisme général de génération.

Les constructions doivent provenir :

- de données ;
- de DOP ;
- d’alignements appris ;
- éventuellement d’un générateur linguistique externe.

---

## 25.3 Pas d’ontologie maison écrite à la main comme cœur

TRIPS apporte une ontologie linguistique utile à l’interprétation.

Elle est une **source d’évidence et de bootstrap**.

Seman2 ne doit pas transformer celle-ci automatiquement en vérité ontologique finale.

---

## 25.4 Pas de perte des analyses alternatives

Ne jamais garder uniquement :

```text
best_parse
```

si l’analyseur fournit des alternatives pertinentes.

---

## 25.5 Pas de pipeline irréversible

Ne jamais :

```text
raw → normalized → semantic → delete raw
```

---

## 25.6 Pas de deuxième architecture parallèle

Ne pas créer :

```text
semantic_engine/
dialogue_engine/
tone_engine/
generation_engine/
world_model/
```

avec des modèles incompatibles.

Tout doit converger dans les structures génériques du niveau 3.

---

## 25.7 Pas de POC historique automatiquement réintégrée

Aucun composant de l’ancien Seman2 n’entre dans le nouveau cœur simplement parce qu’il existe.

Critère :

> Ce composant respecte-t-il la Constitution et remplace-t-il réellement une fonction encore nécessaire ?

Sinon : archive.

---

# 26. Technologies choisies — détails

## 26.1 Python

Rôle :

- orchestration ;
- ingestion ;
- adapters ;
- conversion de formats ;
- tests ;
- scheduling ;
- expérimentation ;
- interfaces vers les outils externes.

Python ne doit pas devenir un endroit où l’on encode les connaissances métier.

---

## 26.2 TRIPS

Rôle :

- parser principal ;
- LF ;
- syntaxe profonde ;
- sémantique ;
- ontologie linguistique ;
- contexte discursif selon les composants déployés ;
- référence ;
- paragraphes / dialogue.

Adapter Seman2 requis :

```text
TRIPS output
   ↓
Seman2 AnalysisBundle
   ├── semantic projection
   └── structural projection
```

Cet adapter doit être **le plus lossless possible**.

---

## 26.3 disco-dop

Rôle :

- recevoir les structures grammaticales observées ;
- extraire des fragments ;
- calculer les fréquences/probabilités ;
- proposer des recombinaisons et régularités structurelles.

Le format DOP doit conserver une référence aux unités d’évidence d’origine.

---

## 26.4 AtomSpace

Rôle :

- graphes ;
- hypergraphes ;
- valeurs ;
- patterns ;
- variables ;
- requêtes ;
- provenance structurée ;
- liens entre semantic/structural/context.

Seman2 doit définir une **mince convention d’encodage**, pas une énorme ontologie.

---

## 26.5 OpenCog Miner

Rôle :

- rechercher des motifs récurrents ;
- fournir des candidats d’abstraction.

Le Miner produit des **candidats**.

Il ne décide pas la signification humaine.

---

## 26.6 ERG + ACE + PyDelphin

Rôle :

- oracle grammatical ;
- validation ;
- benchmark ;
- diagnostics sur les constructions difficiles.

Non-runtime par défaut.

---

## 26.7 SQLite

Rôle :

- journal immutable-ish ;
- suivi des jobs ;
- provenance de traitement ;
- replay.

---

# 27. Pourquoi OpenCog Learn n’est pas le pipeline principal

OpenCog Learn reste une source importante d’idées et éventuellement de composants.

Cependant le nouveau Seman2 ne lui délègue pas toute l’acquisition linguistique parce que :

- nous choisissons une linguistique classique profonde comme bootstrap ;
- TRIPS fournit déjà une interprétation riche ;
- DOP apprend directement sur les analyses ;
- Seman2 veut concentrer son apprentissage sur les structures de niveau supérieur et leur correspondance au sens.

OpenCog Learn peut être réévalué plus tard comme :

- source d’algorithmes ;
- comparaison ;
- mécanisme complémentaire.

Pas comme dépendance obligatoire du chemin critique initial.

---

# 28. Pourquoi Link Grammar n’est plus le parser principal

Link Grammar reste un excellent outil et un projet remarquable pour l’apprentissage structurel.

Mais pour le morceau #1 recherché, Seman2 veut immédiatement :

- analyse grammaticale profonde ;
- sémantique ;
- rôles ;
- ontologie ;
- événements ;
- contexte ;
- dialogue/référence.

TRIPS couvre une plus grande partie de cette chaîne dans un même écosystème.

Link Grammar peut rester un outil expérimental secondaire si un besoin concret apparaît.

---

# 29. Pourquoi ULF/EL n’est pas obligatoire au départ

ULF/EL est intellectuellement très proche de plusieurs objectifs de Seman2.

Mais ajouter immédiatement :

```text
TRIPS LF
→ ULF
→ EL
→ Seman2
```

créerait une couche de conversion substantielle avant même d’avoir démontré qu’elle est nécessaire.

Principe :

> aucune représentation supplémentaire sans déficit concret démontré.

Si plus tard une opération exige une expressivité qu’on ne peut raisonnablement obtenir des structures actuelles, ULF/EL pourra être réévalué.

---

# 30. Pourquoi il n’y a pas 50 layers

Tous les mécanismes suivants vivent dans les trois niveaux :

| Capacité | Où elle vit |
|---|---|
| Ingestion | Niveau 1 |
| Provenance brute | Niveau 1 |
| Syntaxe | Niveau 2 |
| Sémantique initiale | Niveau 2 |
| Référence/discours initial | Niveau 2 |
| Fragments DOP | Niveau 3 |
| Concepts | Niveau 3 |
| Abstractions | Niveau 3 |
| Schemas | Niveau 3 |
| Dialogue appris | Niveau 3 |
| Ton/style appris | Niveau 3 |
| Mémoire | Niveau 3 |
| QA | utilisation du Niveau 3 |
| Génération | utilisation inverse du Niveau 3 |
| Révision | opération du Niveau 3 |
| Raisonnement | opérations génériques sur Niveau 3 |

---

# 31. Compréhension détaillée

Lorsqu’un nouveau texte arrive :

```text
RAW
 ↓
EvidenceUnit
 ↓
TRIPS
 ↓
AnalysisBundle
 ├─ semantic candidates
 └─ structural candidates
 ↓
lookup existing patterns
 ↓
find alignments
 ↓
compare context
 ↓
rank
 ↓
new learned structures / updated hypotheses
```

Le résultat de compréhension n’est pas nécessairement un objet unique.

Il peut être :

```text
InterpretationSet
  H1 score .52
  H2 score .31
  H3 score .17
```

---

# 32. Génération détaillée

La génération commence avec une structure à communiquer, non avec une phrase template.

```text
semantic target
+
dialogue context
+
desired contextual constraints
 ↓
retrieve compatible alignments
 ↓
retrieve structural fragments
 ↓
compose candidate structures
 ↓
rank according to observed usage
 ↓
grammatical validation/realization
 ↓
surface string
```

Les préférences de ton et de registre ne sont pas nécessairement des labels.

Elles peuvent être des contraintes contextuelles proches de clusters observés.

---

# 33. Bootstrapping

Un système totalement vierge est inutilement handicapé.

Seman2 peut utiliser comme bootstrap :

- la grammaire TRIPS ;
- le lexique TRIPS ;
- l’ontologie TRIPS ;
- les analyses grammaticales ;
- éventuellement des corpora treebankés ;
- connaissances lexicales externes si nécessaire.

Mais toutes ces sources doivent conserver leur provenance.

Le système doit distinguer :

```text
learned_from_corpus
imported_from_TRIPS
imported_from_external_lexicon
inferred
user_asserted
```

---

# 34. L’abstraction n’est pas limitée à la langue

Le même mécanisme générique :

```text
observe
→ align
→ detect recurring structure
→ generalize
→ reuse
```

peut servir à découvrir :

- structures linguistiques ;
- concepts du monde ;
- événements complexes ;
- relations causales ;
- habitudes ;
- scripts ;
- interactions conversationnelles ;
- styles.

C’est précisément pourquoi le runtime doit rester générique.

---

# 35. Critères de réussite du nouveau Seman2

Le projet n’est pas jugé sur le nombre de modules.

Il est jugé sur les comportements émergents.

## 35.1 Test A — structure

Après ingestion d’un corpus, le système doit pouvoir retrouver des fragments récurrents non codés à l’avance.

---

## 35.2 Test B — alignement

Deux structures de surface différentes exprimant une organisation sémantique proche doivent pouvoir converger vers des alignements similaires.

---

## 35.3 Test C — abstraction

Plusieurs instances partageant une structure doivent produire un pattern général réutilisable.

---

## 35.4 Test D — nouveau concept sans code

Introduire un ensemble de textes sur un concept jamais rencontré.

Succès si :

- les nouvelles structures sont créées ;
- elles se relient aux structures existantes ;
- aucune modification de code n’est requise.

---

## 35.5 Test E — contexte rétroactif

Une phrase ambiguë reçoit plusieurs hypothèses.

Une phrase suivante désambiguïse.

Succès si :

- l’évidence précédente reste intacte ;
- les scores changent ;
- les dérivations dépendantes peuvent être réévaluées.

---

## 35.6 Test F — génération par réutilisation

Après observation de constructions, le système doit pouvoir produire une formulation nouvelle en combinant des structures apprises, sans template spécifique au concept.

---

## 35.7 Test G — style/discours émergent

Après exposition à des corpus différenciés, le système doit découvrir des associations entre :

- formes ;
- contextes ;
- séquences ;
- réactions.

Sans avoir reçu un enum de styles.

---

# 36. Tests anti-hardcoding

Ces tests sont obligatoires.

## Test 1

Chercher dans le code :

```text
REQUEST
TRANSFER
DOG
QUESTION
SARCASTIC
PASSIVE
POSSESSION
```

Leur présence dans les tests/fixtures est acceptable.

Leur présence comme branches métier du runtime doit déclencher une revue.

---

## Test 2

Inventer un prédicat/concept totalement artificiel dans le corpus.

Le système doit pouvoir l’apprendre sans modification de code.

---

## Test 3

Inventer une construction linguistique artificielle régulière.

Le système doit pouvoir accumuler des fragments/alignements sans nouveau handler.

---

## Test 4

Changer les étiquettes humaines utilisées dans les données.

Le comportement algorithmique doit rester identique.

---

# 37. Structure proposée du nouveau projet

```text
seman2-next/
│
├── CONSTITUTION.md
├── ARCHITECTURE.md
├── NO-GO.md
├── README.md
│
├── src/
│   ├── evidence/
│   │   ├── store.py
│   │   ├── stream.py
│   │   └── provenance.py
│   │
│   ├── interpretation/
│   │   ├── model.py
│   │   ├── trips_adapter.py
│   │   └── projections.py
│   │
│   ├── learning/
│   │   ├── structures.py
│   │   ├── alignments.py
│   │   ├── patterns.py
│   │   ├── ranking.py
│   │   └── revision.py
│   │
│   └── runtime/
│       ├── engine.py
│       └── operations.py
│
├── adapters/
│   ├── trips/
│   ├── atomspace/
│   ├── discodop/
│   └── erg_oracle/
│
├── data/
│   └── evidence.sqlite
│
└── tests/
    ├── constitutional/
    ├── linguistic/
    ├── induction/
    ├── discourse/
    └── generation/
```

### Attention

Même cette arborescence est une suggestion technique.

Elle ne doit pas dégénérer en dizaines de sous-moteurs.

---

# 38. Ce qui est archivé de l’ancien Seman2

L’ancien Seman2 devient une archive de recherche.

À conserver :

- documentation ;
- observations ;
- benchmarks ;
- corpus de tests ;
- résultats de POC ;
- cas limites ;
- décisions et échecs utiles.

À ne pas importer automatiquement :

- runtime ;
- modèles métier ;
- règles hardcodées ;
- hiérarchies conceptuelles ;
- handlers ;
- formats figés ;
- moteurs temporels spécialisés ;
- structures de génération artisanales.

---

# 39. Ordre d’implémentation

## Phase 0 — squelette

Créer :

- Constitution ;
- Evidence store ;
- modèles génériques ;
- tests anti-hardcoding.

---

## Phase 1 — TRIPS lossless adapter

Objectif :

```text
text
→ TRIPS
→ full captured output
→ Seman2 AnalysisBundle
```

Aucune induction encore.

Critère :

> aucune information importante de TRIPS ne doit être perdue arbitrairement.

---

## Phase 2 — double projection

Construire :

```text
AnalysisBundle
  ├─ SemanticProjection
  └─ StructuralProjection
```

avec liens croisés vers les spans.

---

## Phase 3 — DOP

Envoyer les structures vers disco-dop.

Vérifier :

- fragments ;
- fréquences ;
- réutilisation ;
- reconstruction.

---

## Phase 4 — AtomSpace

Encoder :

- evidence refs ;
- structures ;
- patterns ;
- alignments ;
- provenance.

Le schéma doit rester minimal.

---

## Phase 5 — alignement automatique

Construire le mécanisme qui exploite les correspondances de spans et de structures pour proposer :

```text
structural slot ↔ semantic slot
```

---

## Phase 6 — induction

Introduire :

- Miner ;
- regroupements ;
- généralisations ;
- scores ;
- abstraction multi-niveaux.

---

## Phase 7 — contexte multi-phrase

Tester :

- pronoms ;
- ellipses ;
- références ;
- ambiguïtés ;
- révision.

---

## Phase 8 — dialogue

Ingérer de vrais dialogues.

Ne rien coder spécialement pour :

```text
question
answer
greeting
request
```

Observer ce qui peut être appris.

---

## Phase 9 — génération

Utiliser les alignements et constructions en sens inverse.

Le premier objectif n’est pas l’élégance.

Le premier objectif est :

> produire une structure linguistique nouvelle par recombinaison de connaissances apprises sans handler spécifique.

---

# 40. Première définition de « morceau #1 terminé »

Le morceau #1 est considéré terminé lorsque :

1. Seman2 peut ingérer continuellement du texte.
2. Le texte est journalisé sans perte.
3. TRIPS l’analyse.
4. Plusieurs phrases peuvent être soumises avec contexte.
5. Les résultats complets sont conservés.
6. La branche sémantique est produite.
7. La branche structurale est produite.
8. Les deux branches conservent leurs correspondances de spans.
9. Une nouvelle analyse peut réviser une hypothèse antérieure.
10. Aucun concept métier propre à Seman2 n’a dû être codé.

---

# 41. Définition de « architecture réussie »

Le nouveau Seman2 réussit si, après suffisamment d’exposition :

```text
texte
  ↓
structures linguistiques observées
  ↕
structures sémantiques observées
  ↓
motifs récurrents
  ↓
alignements
  ↓
abstractions
  ↓
concepts / schémas / constructions
  ↓
compréhension améliorée
  ↓
génération
  ↓
nouvelles observations
  ↓
apprentissage continu
```

et si cette boucle fonctionne sans transformer chaque découverte en nouvelle logique codée.

---

# 42. Formulation canonique de l’esprit Seman2

> **Seman2 reçoit du langage comme évidence, utilise la meilleure linguistique disponible pour en exposer simultanément la structure et les représentations sémantiques candidates, conserve les deux sans destruction, puis apprend par répétition, alignement et généralisation quelles structures du langage correspondent à quelles structures du monde et dans quels contextes elles sont utilisées. Les abstractions apprises deviennent elles-mêmes des objets manipulables et peuvent être combinées en abstractions d’ordre supérieur. Les mêmes connaissances servent ensuite à comprendre de nouvelles observations et, dans la direction inverse, à générer du langage. Aucune catégorie sémantique, discursive ou stylistique apprise ne doit devenir une primitive du runtime.**

---

# 43. Phrase de contrôle pour tout agent de programmation

Avant toute implémentation, l’agent doit appliquer ce test :

> **Est-ce que je suis sur le point de coder une connaissance que Seman2 devrait plutôt pouvoir représenter ou apprendre ?**

Si oui :

**STOP.**

La connaissance doit devenir une structure de données.

---

# 44. Références technologiques principales

- TRIPS Parser / NLU : https://trips.ihmc.us/parser/
- TRIPS parsing systems : https://trips.ihmc.us/parsing/
- TRIPS Web API : https://trips.ihmc.us/parser/api.html
- TRIPS Cogent : https://trips.ihmc.us/cogent/
- disco-dop : https://github.com/andreasvc/disco-dop
- OpenCog AtomSpace : https://github.com/opencog/atomspace
- OpenCog Miner : https://github.com/opencog/miner
- English Resource Grammar : https://github.com/delph-in/erg
- PyDelphin : https://github.com/delph-in/pydelphin

---

# 45. Décision architecturale finale

Le nouveau Seman2 n’est pas :

- un nouveau parser ;
- une nouvelle grammaire anglaise ;
- une ontologie écrite à la main ;
- un moteur de dialogue à handlers ;
- un moteur de templates ;
- une collection de POC empilées.

Le nouveau Seman2 est :

> **un système générique qui conserve l’évidence, observe simultanément le sens et la forme grâce à un interpréteur linguistique profond, puis apprend les correspondances, régularités et abstractions qui permettent progressivement de comprendre le monde, comprendre l’usage du langage et produire du langage.**

Architecture :

```text
              NIVEAU 1
          FLUX D'ÉVIDENCE
                  │
                  ▼
              NIVEAU 2
      INTERPRÉTATION LINGUISTIQUE
             ┌────┴────┐
             ▼         ▼
           SENS     STRUCTURE
             │         │
             └────┬────┘
                  ⇅
              NIVEAU 3
         MODÈLE APPRIS COUPLÉ
     concepts ⇄ alignements ⇄ constructions
                  ⇅
        compréhension / génération
```

**Trois niveaux. Deux projections. Un seul modèle appris. Aucune connaissance métier codée en dur.**
