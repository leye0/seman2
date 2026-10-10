# Induction grammaticale par lésion contrôlée

La grammaire complète n'a servi qu'à sélectionner les cas lésés et à noter la récupération. Les hypothèses ont été produites exclusivement depuis les forêts de la grammaire masquée. Les productions injectées sont syntaxiques et n'apprennent aucune action sémantique.

## Sweeps

- Première passe : 12 configurations.
- Passe ciblée : 4 configurations.
- Configuration gagnante : `waiting-l3-s2-fnone-n4-g1`.
- Temps total : 289.89 s.

## Résultat gagnant

- Hypothèses injectées : 12
- Signatures masquées retrouvées : 0
- Analyses inédites récupérées en validation : 19
- Faux positifs contre la grammaire complète : 0
- Activations sur contre-exemples proches : 18

## Meilleures règles

### relative_attachment

- `NP -> NP COMMA` — support 11; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - A place could stay the same while everything about a person's experience of it changed.
- `ADVP -> NP COMMA` — support 11; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - A place could stay the same while everything about a person's experience of it changed.
- `CLAUSE -> NP COMMA` — support 11; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - A place could stay the same while everything about a person's experience of it changed.
- `VP -> NP COMMA` — support 11; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - A place could stay the same while everything about a person's experience of it changed.
Validation récupérée : 6/7; activations sur contrôles : 6.

### nominal_pp_attachment

- `ADVP -> NP COMMA` — support 10; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.
- `CLAUSE -> N COMMA` — support 10; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.
- `CLAUSE -> NP COMMA` — support 10; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.
- `VP -> N COMMA` — support 10; hypothèse équivalente ou concurrente.
  - Maya could find the cafeteria without looking at a sign.
  - Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.
Validation récupérée : 7/7; activations sur contrôles : 6.

### np_coordination

- `CLAUSE -> NP COMMA` — support 11; hypothèse équivalente ou concurrente.
  - At the corner, Maya stopped beside Mom and pointed across the street.
  - Symbols and labels make a useful map; directions and distances keep it from becoming only a picture.
- `VP -> NP COMMA` — support 10; hypothèse équivalente ou concurrente.
  - At the corner, Maya stopped beside Mom and pointed across the street.
  - Symbols and labels make a useful map; directions and distances keep it from becoming only a picture.
- `VP-NP -> NP COMMA` — support 10; hypothèse équivalente ou concurrente.
  - At the corner, Maya stopped beside Mom and pointed across the street.
  - Symbols and labels make a useful map; directions and distances keep it from becoming only a picture.
- `PP -> NP COMMA` — support 10; hypothèse équivalente ou concurrente.
  - At the corner, Maya stopped beside Mom and pointed across the street.
  - Symbols and labels make a useful map; directions and distances keep it from becoming only a picture.
Validation récupérée : 6/7; activations sur contrôles : 6.

## Lecture des échecs et prochaine étape

Les configurations `waiting` ne voient que les catégories explicitement attendues; les constructions d'attachement exigent le signal `bridge` ou `suffix`. Les activations sur contrôles mesurent la surgénéralisation syntaxique, mais une validation négative plus forte devra apprendre quelles contraintes de traits et quels contextes de tête conserver. La prochaine amélioration prometteuse est une anti-unification des environnements de traits des états partiels, puis l'apprentissage séparé des actions sémantiques.
