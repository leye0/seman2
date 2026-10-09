# Protocole

Les 849 graphes sont ingérés sous trois permutations déterministes et comparés
au regroupement batch exact. Les préfixes 100/300/849 mesurent la croissance.
Le protocole vérifie aussi snapshot/rechargement, doublons et invalidation
tardive d'un composant déjà promu.

Critères : égalité batch, zéro variation du nombre de composants entre ordres
et moins de 50 % des comparaisons toutes-paires.

