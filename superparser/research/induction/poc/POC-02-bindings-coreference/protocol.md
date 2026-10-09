# Protocole

## Matière testée

Le manifeste sépare deux familles.

1. Des DAG synthétiques minimaux isolent les variations de taille : NP simple
   versus NP avec déterminant, NP relative tenue à l'écart, VP simple versus
   coordination, VP auxiliaire tenue à l'écart et contraste de négation.
2. Des sorties réelles de `DiscourseProcessor` portent les récits `John found
   a key. He kept it.` et `Mary found a coin. She kept it.`. Le récit `Robert
   found a map. He kept it.` reste tenu à l'écart.

Le synthétique localise les erreurs d'alignement. Les mini-discours vérifient
le contrat sur les mentions et liens réellement produits par le parseur.

## Invariants

1. Un port reconstruit exactement chacun de ses sous-graphes sources.
2. Un port n'est créé que sous une racine structurelle commune.
3. Sa catégorie est constante et vérifiée au matching.
4. Une occurrence répétée du même port conserve l'identité du nœud.
5. Une différence de négation, modalité, voix ou autre trait protégé est
   rejetée avant création du port.
6. Les variables créées par une tentative exacte abandonnée sont supprimées.
7. Chaque arête référentielle reconstruite conserve son type et sa règle.
8. `MAYBE_REF` reste `MAYBE_REF` : aucun antécédent n'est choisi.
9. Les ports `REF_SOURCE` et `REF_TARGET` reconstruisent les mentions sources.
10. Un nouveau récit peut matcher plusieurs alternatives simultanément.

## Mesures

- taux de reconstruction exacte des cas de sous-graphes positifs ;
- couverture de reconstruction des arêtes référentielles observées ;
- proportion de motifs référentiels restés ouverts ;
- transfert sur structures et récit tenus à l'écart ;
- rejet du contraste protégé ;
- latence et pic d'allocations de l'opération d'induction uniquement.

Le temps de parsing n'est pas inclus dans la latence POC-02.

## Critère de sortie

- 100 % de reconstruction des sous-graphes positifs ;
- 100 % de couverture des alternatives référentielles de l'oracle structurel ;
- aucune conversion de `MAYBE_REF` en référence résolue ;
- transfert positif sur les trois exemples tenus à l'écart ;
- rejet du contraste de négation ;
- limites et incertitudes documentées.
