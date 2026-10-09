# Analyse

## Tests contrôlés

Les cinq tests ciblés couvrent l'ajout d'un adverbe, la reconstruction des
résidus, le contraste de négation, l'ordre des arguments, le rejet des feuilles
isolées et la stabilité du classement. Ils passent tous.

## Passage sur le cache compact

Sur les 100 premières paires consécutives ayant la même catégorie racine :

- 9 alignements satisfont les seuils v0.1 ;
- 9/9 reconstruisent exactement les deux arbres ;
- couverture médiane des alignements retenus : 42,86 % ;
- temps total d'alignement des 100 paires : 56,082 ms.

L'absence de candidat pour 91 paires est normale : le POC ne force pas une
analogie lorsque les contraintes ou le minimum structurel ne sont pas atteints.

## Limite

La vue v0.1 est un arbre imbriqué. Une réentrance du DAG serait développée dans
ce snapshot et son identité devrait être restaurée explicitement dans une
tranche ultérieure. POC-02 reste l'autorité pour les contraintes de référence.

