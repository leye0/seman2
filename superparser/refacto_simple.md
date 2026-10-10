Dans `seman2/superparser`, implémente un moteur de reconnaissance grammaticale vectoriel, directement intégré au parsing existant.

**1. Vectoriser les mots**

Pour chaque mot, récupérer toutes ses catégories grammaticales possibles depuis WordNet et notre lexique.

Exemple :

`The man is breaking the hammer`

Devient :

`[DET] [N|V] [AUX|COP] [V|ADJ] [DET] [N|V]`

Utilise des bitmasks entiers. Garde les sens et les traits accessibles par référence, sans les développer inutilement.

**2. Vectoriser les 366 règles**

Compiler nos règles grammaticales existantes en motifs de catégories, indexés pour une recherche très rapide.

Par exemple :

`NP → DET N`

`VP → AUX V NP`

`CLAUSE → NP VP`

Le moteur doit trouver les structures compatibles directement par opérations sur les masques, sans énumérer toutes les combinaisons lexicales.

**3. Reconnaître et assembler**

Scanner les vecteurs et reconnaître les constructions connues. Lorsqu'une séquence forme un `NP`, elle peut être utilisée comme `NP` pour reconnaître une construction plus grande.

Recommencer jusqu'à obtenir les structures grammaticales complètes.

Conserver les possibilités concurrentes sous forme de références compactes. Ne pas recopier les arbres, les graphes ou les dérivations à chaque combinaison.

Les contraintes de traits doivent rester applicables pour éviter les correspondances grammaticalement invalides.

**4. Brancher réellement le moteur**

Ce moteur doit effectuer le travail de reconnaissance dans `Parser.parse()`. Il ne doit PAS être un pré-scanner suivi du vieux `Chart` qui refait toute l'analyse.

Réutilise ce qui est pertinent dans l'existant, mais remplace les boucles coûteuses de reconnaissance par les opérations vectorielles et les structures partagées.

La composition sémantique peut rester différée jusqu'à ce qu'une analyse soit demandée.

**5. Mesurer**

Teste quelques phrases simples, une phrase ambiguë et une longue phrase. Vérifie que les analyses principales restent disponibles.

Chronomètre le parsing réel avant/après.

Pas de framework supplémentaire, pas de grosse campagne de tests, pas de documentation interminable.

**Priorité absolue : réduire le nombre d'opérations du moteur.**

Implémente directement. Optimise. Mesure. Fais-moi un court rapport avec les gains obtenus.

Objectif à terme : environ 5 ms par phrase ordinaire, sans prétendre que c'est déjà atteint.