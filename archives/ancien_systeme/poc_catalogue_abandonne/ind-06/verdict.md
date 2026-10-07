# Verdict IND-06

`GO_RECURSIVE_HIERARCHICAL_COMPRESSION` : le pattern de niveau 2 conserve ses
dépendances et dix occurrences originales tout en améliorant la description.
Sur les données réelles IND-01/02/03, le candidat hiérarchique est correctement
reconstruit mais reste non promu, car ses deux supports donnent un gain récursif
négatif une fois le dictionnaire compté.
