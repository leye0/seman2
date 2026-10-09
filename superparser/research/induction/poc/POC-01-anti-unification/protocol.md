# Protocole

## Invariants

1. Chaque candidat reconstruit exactement ses deux racines sources.
2. Une nouvelle racine ne matche que si les constantes et égalités de
   variables sont respectées.
3. Deux occurrences de la même variable restent égales.
4. Deux variables différentes ne sont pas contraintes à être distinctes.
5. L'ordre et le rôle des arêtes enfants sont conservés.
6. Une réentrance ne peut pas être alignée sur deux nœuds distincts.
7. Les différences sur les traits protégés ne deviennent pas des variables.
8. Les spans sont reconstruits mais exclus des variables conceptuelles.
9. Seule l'analyse sélectionnée par POC-00 participe à la généralisation.
10. Un candidat trop général est marqué `trivial` et n'est jamais promu ici.

## Critère de sortie

- reconstruction exacte à 100 % sur le manifeste ;
- réussite des transferts lexicaux tenus à l'écart ;
- rejet des paires structurellement incompatibles ;
- coûts et nombre de variables publiés ;
- aucun recours aux types ou rôles sémantiques retirés par le POC-00.

