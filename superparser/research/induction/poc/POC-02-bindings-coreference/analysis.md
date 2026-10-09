# Analyse

## Résultats

Le manifeste comprend deux cas positifs de sous-graphes, un contraste négatif
et une paire de mini-discours issue du parseur réel.

- reconstruction exacte des ports : **2/2 (100 %)** ;
- transfert sur NP relative et VP auxiliaire : **2/2** ;
- contraste de négation : **rejeté**, comme attendu ;
- alternatives observées : **7 à gauche, 7 à droite** ;
- couverture de reconstruction référentielle : **100 %** des deux côtés ;
- motifs référentiels généralisés : **13**, tous `MAYBE_REF` ;
- correspondances sur le récit tenu à l'écart : **22** ;
- attentes globales : **4/4 (100 %)** ;
- latence médiane d'induction : **0,451 ms**, p95 **2,729 ms** ;
- pic d'allocations : **0,053 MB**.

Les temps excluent volontairement le parsing et mesurent seulement les
opérateurs du POC-02. Le petit manifeste sert de test mécaniste, pas de mesure
de montée en charge.

## Ports de sous-graphe

La structure commune reste explicite et seule la branche incompatible devient
opaque. Le port garde une substitution complète par exemple et impose sa
catégorie au transfert. Une réentrance du port impose aussi l'identité du nœud
matché, pas seulement l'égalité de deux snapshots fortuitement identiques.

Cette interface est sûre mais large : un port NP accepte toute NP. Le POC-03
devra pénaliser les ports trop permissifs par leur coût et leur réutilisation ;
le POC-05 pourra comparer plusieurs frontières d'alignement.

## Références candidates

Le parseur expose plusieurs arêtes `MAYBE_REF` pour chaque pronom. Le POC ne
choisit pas entre l'événement, le nom propre et l'indéfini : il généralise les
formes des deux extrémités et conserve le type de l'arête. Les 22 matches sur
le récit tenu à l'écart sont donc des candidats, pas 22 décisions.

La reconstruction à 100 % signifie « aucune contrainte observée perdue » au
niveau de chaque arête. Elle ne prouve ni que les candidats sont linguistiquement
corrects, ni qu'un cluster global de coréférence a été appris.

## Limites assumées

Les motifs référentiels sont indépendants les uns des autres. Ils ne codent
pas encore les alternatives mutuellement exclusives, les probabilités, ni une
identité globale à travers plusieurs phrases. De même, un port de composant
n'existera qu'après la bibliothèque du POC-03.
