# Analyse

## Corpus répétitif avec exceptions

La bibliothèque promeut exactement deux composants. Les 2 400 occurrences
régulières les utilisent ; les 100 exceptions restent brutes.

| Système | Longueur (bits) |
|---|---:|
| `B0` brut | 9 152 115 |
| `B1` dictionnaire exact | 9 182 138 |
| `B2` meilleur composant unique | 5 227 395 |
| `B3` bibliothèque | 1 321 542 |

`B3` coûte **14,44 %** de `B0`, modèle compris. Le modèle représente 6 857
bits et les données 1 314 685 bits. La reconstruction est de 100 %.

La bibliothèque gelée encode les 600 combinaisons lexicales inédites sans
exception : 280 475 bits contre 2 296 131 bits bruts, soit un ratio de
**12,22 %**, avec reconstruction à 100 %.

## Contrôles négatifs

Sur les 1 000 structures uniques, aucun composant n'est promu. `B3` coûte
1 001 bits de plus que `B0`, car le flux paie explicitement son en-tête et un
bit de mode par exception. Ce résultat négatif est conservé au lieu de choisir
a posteriori une représentation gratuite.

Sur les 1 000 motifs à 40 traits ouverts, le plafond préenregistré de 0,65
rejette les propositions sur-variables. Aucun composant n'est promu et le même
surcoût explicite de 1 001 bits apparaît.

## Ablation

`B1` montre que la fréquence exacte n'aide pas lorsque chaque combinaison
lexicale est nouvelle. `B2` compresse une famille mais laisse l'autre et les
exceptions au brut. Le gain supplémentaire de `B3` provient donc bien de la
bibliothèque multi-composants, pas seulement d'une anti-unification isolée.

Cela ne démontre aucune connaissance sémantique : les règles grammaticales et
les constantes structurelles suffisent à expliquer la compression observée.

## Ressources

Sous `tracemalloc`, l'entraînement des 2 500 observations répétitives prend
13,664 s et atteint 14,406 MB d'allocations suivies. Les cas uniques et
sur-variables prennent respectivement 1,728 s et 2,914 s. Le temps comprend la
sélection, le matching, le calcul des quatre baselines et la vérification du
décodage, mais pas la génération préalable du corpus.

## Risques reportés

La recherche est gloutonne, sensible à la fenêtre de graines et non optimale
globalement. Le POC n'étudie qu'un seed et des familles faciles à séparer par
règle. La composition récursive, les collisions de frontières et la stabilité
à l'ordre deviennent les questions centrales du POC-04/05.
