# Protocole initial

## Invariants testés

1. Tous les identifiants et toutes les sérialisations sont déterministes.
2. Chaque arête référence deux nœuds existants.
3. Les enfants d’un constituant sont ordonnés sans trou.
4. Le graphe `CHILD` est acyclique.
5. Les spans des tokens reconstruisent exactement leur texte source.
6. Une observation contient au plus une racine et aucune forêt.
7. La sélection existante du parseur est utilisée lorsqu'elle existe.
8. Une sélection structurelle de repli est déterministe et marquée provisoire.
9. Une différence de négation produit une observation différente.
10. Les champs sémantiques et la provenance WordNet sont refusés.

## Définition du round-trip dans cette tranche

Le round-trip porte sur la **projection structurelle autorisée** : tokens,
lexèmes, arbre sélectionné, règles, enfants, mentions et références. Il ne prétend pas
reconstruire les données explicitement exclues (graphes sémantiques, scores,
bindings runtime, sens WordNet), la forêt ou les analyses non sélectionnées.

## Critère de sortie restant

Le verdict ne pourra être posé qu’après ajout de fixtures couvrant portée,
enchâssement, ambiguïtés, coréférence candidate et après benchmark de coût sur
un corpus versionné.

