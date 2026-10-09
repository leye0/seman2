# Protocole

## Invariants

1. Chaque alignement reconstruit exactement ses deux arbres sources.
2. Toute branche non appariée demeure un résidu sérialisé du bon côté.
3. L'ordre des dépendances est conservé ; aucun appariement croisé n'est permis.
4. Les mots identiques à des positions grammaticales différentes ne sont pas
   rapprochés en traversant les dépendances.
5. Les traits grammaticaux protégés incompatibles interdisent l'alignement du
   nœud concerné.
6. Une ressemblance lexicale sans relation partagée ne suffit pas.
7. Les identifiants et le classement sont déterministes.
8. Les coûts dépendent des valeurs logiques, pas de la taille du JSON.

## Politique initiale

- insertion ou suppression : un coût par nœud résiduel ;
- substitution : 0,25 par valeur différente ;
- au moins une arête structurelle partagée ;
- couverture minimale de 25 % du plus grand arbre.

Ces seuils servent au POC et ne constituent pas une politique linguistique
définitive.

