# Analyse compacte v0.2

## Résultat sur le corpus réel

Les 500 premières lignes de *The Map of Everything* produisent 849 phrases ou
fragments :

- 849/849 observations possèdent un arbre sélectionné ;
- 827 utilisent `parser_best` et 22 un repli structurel provisoire ;
- le cache JSONL complet occupe 20 996 244 octets ;
- POC-01 à POC-04 lisent tous cette représentation sans reparsing.

La forêt complète précédemment cachée a été supprimée et reconstruite dans ce
format compact.

## Corpus minimal v0.1

Neuf cas : transitif simple, négation, modalité, question WH, enchâssement,
coordination, ambiguïté d'attachement et séquence anaphorique de deux phrases.

Résultats de l'exécution de sortie :

- round-trip canonique et structurel : **9/9 (100 %)** ;
- attentes du parseur : **9/9 (100 %)** ;
- candidats référentiels sur `He opened it.` : **7** ;
- latence de projection médiane : **97,367 ms** ;
- p95 sur les neuf cas : **301,972 ms** ;
- pic d'allocations d'une projection : **6,433 MB** ;
- plus grand graphe : **1 196 nœuds / 2 155 arêtes / 546 451 octets JSON**.

Le premier parsing inclut le chargement froid de WordNet et n'est pas une
mesure du POC. La latence de projection est mesurée sans `tracemalloc`; les
allocations sont mesurées lors d'une seconde projection instrumentée.

## Observation principale

La décontamination ne consiste pas seulement à retirer `semantic_type`. Les
identifiants de sens, glosses, fichiers WordNet, scores, handles et bindings
runtime peuvent également révéler ou transporter des distinctions externes.
La projection fonctionne donc par liste blanche.

Le corpus a effectivement trouvé `semantic_type=POSSESSOR` imbriqué dans les
traits d'un constituant lors du cas d'attachement. Le filtre récursif l'élimine
maintenant et la validation refuse toute réintroduction du champ.

## Limite actuelle

Le graphe reconstruit fidèlement l'arbre choisi, pas le `ParseResult` intégral.
Cette limite est intentionnelle. Le texte source permet de relancer le parseur
si une expérience future nécessite une autre sélection.

