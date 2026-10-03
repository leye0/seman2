# POC central — Composition sémantique, identité et projection d’état

## Objectif

Vérifier qu’une suite d’énoncés peut :

- créer des entités particulières ;
- conserver leur identité à travers plusieurs phrases ;
- leur associer des propriétés et des relations ;
- appliquer plusieurs transformations successives ;
- maintenir l’ordre temporel de ces transformations ;
- permettre d’interroger correctement l’état final obtenu.

Ce POC vise directement le cœur du moteur symbolique : construire un monde mental explicite à partir d’observations linguistiques, puis faire évoluer ce monde de manière cohérente.

---

## Exemple 1 — Propriété qualitative

Entrée :

```text
Jack est lent comme une tortue.
```

Le système ne doit pas simplement produire une relation textuelle ou lexicale.

Il doit être capable de construire une entité particulière :

```text
Entity Jack_17
```

puis une structure de propriété correspondant à la dimension de vitesse :

```text
PropertyInstance P81
    bearer = Jack_17
    dimension = speed
    value = LOW
```

avec, selon les analyses disponibles :

```text
simile(Jack_17, tortoise)
tortoise associated_with low_speed
```

Requête :

```text
speed(Jack_17) = ?
```

Résultat attendu :

```text
LOW
```

Aucune valeur numérique ne doit être inventée si les données ne permettent qu’une interprétation qualitative.

---

## Exemple 2 — Référence, propriété et inversion

Entrée :

```text
Il fait clair dans la chambre de Robert.
C'est l'inverse dans la chambre de Julia.
```

Le système doit créer des entités distinctes :

```text
Robert_1
Julia_1

Room_24
    associated_with Robert_1

Room_51
    associated_with Julia_1
```

Le premier énoncé produit un état :

```text
BrightnessState_1
    bearer = Room_24
    dimension = brightness
    value = HIGH
```

Le deuxième énoncé doit résoudre :

```text
"C'"
    ↓
référence à l'état ou à la propriété précédente

"inverse"
    ↓
opérateur sur la même dimension

"chambre de Julia"
    ↓
nouvelle entité Room_51 liée à Julia_1
```

Transformation :

```text
inverse(HIGH on brightness dimension)
    ↓
LOW
```

État résultant :

```text
brightness(Room_51) = LOW
```

Requête :

```text
brightness(Room_51) = ?
```

Résultat attendu :

```text
LOW
```

---

## Le moteur comme système de transitions d’état

Le comportement général attendu est :

```text
Observation linguistique
        ↓
structures candidates
        ↓
bindings d'entités
        ↓
Current World / Active Graph
        ↓
Transformation_1
        ↓
Transformation_2
        ↓
Transformation_3
        ↓
New Graph State
        ↓
requête sur l'état résultant
```

Les transformations peuvent modifier :

- des propriétés ;
- des relations ;
- des localisations ;
- des possessions ;
- des états binaires ou qualitatifs ;
- des contraintes ;
- des bindings ;
- des relations temporelles.

Le graphe doit conserver l’identité des objets concernés pendant toute la séquence.

---

## Fixtures complémentaires

### Possession et déplacement

```text
Marie pose le livre sur la table.
Jean prend le livre.
Il le donne à Luc.
```

Résultat final attendu :

```text
possessor(book) = Luc
location(book) != table
```

### Relations transitives

```text
Paul est plus grand que Marc.
Marc est plus grand que Jules.
```

Résultat attendu :

```text
Paul > Jules on height dimension
```

### État temporel

```text
Julie entre dans sa chambre.
Elle allume la lampe.
Puis elle l'éteint.
```

Résultat final attendu :

```text
state(lamp) = OFF
```

Le système doit conserver l’ordre des transformations et ne pas retourner l’état intermédiaire `ON`.

---

# CORE-01A — Moteur symbolique isolé

## But

Tester le moteur sans dépendre encore du NLP.

Les structures d’entrée sont fournies manuellement et sont supposées correctes.

Exemple :

```text
ENTITY Julia_1
ENTITY Room_1
associated_with(Julia_1, Room_1)

STATE brightness(Room_1) = LOW

TRANSFORM increase_brightness(Room_1)
```

Le POC doit tester directement :

```text
bindings
identity
state transitions
temporal order
constraints
contradictions
property updates
relation updates
query of final state
```

Question centrale :

> Si les analyseurs fournissent exactement les structures dont le moteur a besoin, le moteur sait-il maintenir correctement un monde symbolique et ses transformations ?

Ce POC doit être réalisé relativement tôt, dès que la représentation commune, les bindings et les contraintes sont suffisamment définis.

---

# CORE-01B — Intégration bout en bout

## But

Tester la même capacité à partir de langage naturel réel.

Pipeline :

```text
texte naturel
    ↓
ERG / MRS / autres analyses formelles
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

Exemple :

```text
La chambre de Robert est claire.
C'est l'inverse dans celle de Julia.
```

Puis :

```text
Quelle est la clarté de la chambre de Julia ?
```

Le système doit répondre à partir du graphe résultant, pas à partir d’un pattern textuel ad hoc.

CORE-01B valide donc simultanément :

- la création d’entités particulières ;
- la résolution des références ;
- la composition sémantique ;
- la continuité d’identité ;
- l’application des transformations ;
- la mémoire de l’état ;
- les contraintes ;
- la provenance ;
- l’interrogation du graphe final.

---

# Position dans l’ordre des POC

Il ne faut pas attendre que toutes les POC analytiques soient terminées avant toute tentative d’intégration.

Ordre recommandé :

```text
POC analytiques fondamentales
        ↓
GRAPH / bindings / contraintes
        ↓
CORE-01A
        ↓
poursuite des POC individuelles
        ↓
ensemble des POC analytiques terminé
        ↓
CORE-01B
        ↓
développement sérieux du moteur complet
```

CORE-01A sert à vérifier très tôt que le langage interne du système est capable de représenter et transformer correctement des objets persistants.

CORE-01B doit arriver beaucoup plus tard, lorsque les analyseurs et adaptateurs ont démontré les données qu’ils produisent réellement.

---

# Principe central

Le cœur du projet n’est pas seulement de reconnaître ou de générer du langage.

Il est de pouvoir :

> prendre une succession d’observations linguistiques, construire des objets particuliers persistants, transformer leur état, maintenir les relations entre eux et déterminer l’état du monde symbolique résultant.

Le chatbot devient ensuite un moyen de lire, modifier et interroger ce monde symbolique.
