# Analyse

## Résultats

La découverte produit une définition atomique, trois composants intermédiaires
et six composants supérieurs, soit dix objets partagés. La profondeur maximale
est trois et les 3 000 instances sont reconstruites exactement.

| Mesure | Plat | Récursif |
|---|---:|---:|
| Modèle | 25 661 bits | 11 799 bits |
| Données d'entraînement | 1 157 303 bits | 1 157 303 bits |
| Total entraînement | 1 182 964 bits | 1 169 102 bits |
| Données held-out | 316 219 bits | 316 219 bits |

La hiérarchie économise **13 862 bits** sur le modèle complet. Son coût total
est **98,83 %** du modèle plat, soit une réduction de 1,17 %. Le résultat est
petit mais positif avec le coût des dix définitions et de tous les appels.

## Held-out

Les 600 lexicalisations inédites matchent et se reconstruisent à 100 %. Leur
coût marginal est exactement identique dans les deux systèmes : chaque modèle
expose les mêmes variables et les bibliothèques sont déjà payées.

La composition démontre donc ici une factorisation du modèle et une stabilité
de transfert, pas une compression supplémentaire des valeurs nouvelles.

## Liaison et portée

Les mappings inner/outer sont la seule voie de communication entre niveaux.
Deux appels mappés vers `X0` doivent produire la même valeur ; deux mappings
vers `X0` et `X1` peuvent recevoir la même valeur sans contrainte de différence.
Un test négatif modifiant une seule occurrence liée est rejeté.

## Sécurité et explosion

Le graphe de dépendances est validé avant usage, et l'expansion maintient aussi
une pile active. Un cycle `A → B → A` est rejeté. La politique exige un support
minimal de quatre et une profondeur maximale de huit : un assemblage utilisé
une seule fois n'est pas promu même si un gain local lui est attribué.

## Limites

La découverte est exacte : elle reconnaît un sous-gabarit déjà présent, sans
déplacement ni correspondance partielle. Les contextes synthétiques sont
propres et leur frontière est non ambiguë. Le gain dépend entièrement de la
réutilisation structurelle ; aucune utilité inférentielle ou sémantique n'est
démontrée. Ces questions passent au POC-05 et aux phases suivantes.

L'évaluation des 2 400 instances prend 3,433 s sous `tracemalloc`, avec un pic
d'allocations suivi de 0,126 MB ; la construction préalable des gabarits est
hors mesure.
