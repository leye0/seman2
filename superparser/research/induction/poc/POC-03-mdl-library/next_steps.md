# Prochaines étapes

1. POC-04 : permettre à un composant d'appeler d'autres composants sans cycle.
2. Comparer composition plate et récursive avec le même code de description.
3. Ajouter plusieurs seeds et permutations d'ordre pour mesurer la stabilité.
4. Tester la bibliothèque sur des sorties réelles du parseur à plus grande
   échelle, en séparant toujours temps de parsing et temps d'induction.
5. Explorer des politiques Pareto plutôt qu'un unique seuil de ratio variable.
6. Conserver les occurrences et preuves comme journal de données, sans les
   compter deux fois dans `L(M)` et `L(D|M)`.
