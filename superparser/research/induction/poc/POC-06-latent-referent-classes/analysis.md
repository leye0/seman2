# Analyse

Le benchmark contient les 849 observations : 2 756 substitutions
d'entraînement, 623 de validation et 591 de test.

- F1 held-out : **0,3064** ;
- baseline grammaticale `B1/NOUN` : **0,0522** ;
- précision / rappel : **0,2701 / 0,3541** ;
- contextes couverts : **10/23** ;
- familles découvertes : **5**.

Le gain vient de la compatibilité répétée entre positions grammaticales et
lexèmes, mais la couverture reste faible. Le résultat est prédictif, pas une
récupération prouvée de catégories physiques.

La tranche ne prouve pas que les familles correspondent à des catégories du
monde réel. Elles sont des classes extensionnelles de substitution dans le
corpus observé.

