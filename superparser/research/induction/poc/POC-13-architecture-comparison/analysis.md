# Analyse

Le résultat important est une égalité de qualité, pas un classement artificiel.
Les trois architectures partagent donc : F1 référents **0,3064**, zéro
prédiction relationnelle held-out, précision/rappel transitions réelles
**0,4091 / 0,0138**, transfert réel **0,6667 / 0,6667**, quatre composants
incrémentaux et p99 maximal **0,6393 ms**. Le format compact valide 849/849
graphes.

A n'a aucune traversée de frontière mais place les onze capacités dans le même
domaine d'échec. B ajoute une seule frontière et ramène ce rayon à six. C le
ramène à quatre, au prix de trois traversées et d'un service partagé en plus.
Toutes les variantes ont onze implémentations de primitives et **zéro copie**.

Les résultats réels expliquent le choix : le chemin structural/incrémental est
stable, tandis que relation et transition restent NO-GO sur le roman. B sépare
exactement ces régimes expérimentaux. C ne reçoit encore aucun gain de qualité
qui justifierait ses frontières supplémentaires.

Les ablations contrôlées confirment des dépendances, sans constituer un verdict
sur le roman : retirer la composition coûte 13 862 bits à l'entraînement mais
zéro en held-out; retirer la bibliothèque MDL coûte 7 830 573 bits sur le cas
répétitif; retirer les contraintes accepte une généralisation entre polarités;
retirer les deltas fait tomber les alignements inter-constructions de trois à
zéro.
