# Analyse

- épisodes : **2 633**, dont **1 826 train** et **398 test** ;
- hypothèses promues : **6** ;
- prédictions correctes : **9/22** ;
- précision / rappel / F1 : **0,4091 / 0,0138 / 0,0267** ;
- F1 des baselines fréquentielle et syntaxique : **0,000 / 0,000**.

Le signal dépasse les baselines mais échoue au seuil de précision. Il ne
justifie donc ni transition fiable ni causalité.

Sur 180 suites contrôlées temporaires, deux effets sont appris, le F1 held-out
vaut **1,000**, l'abstention sur l'événement contrôle vaut **1,000** et chaque
prédiction conserve sa chaîne de preuve. Ce résultat valide le mécanisme, pas
son extraction depuis le roman.

