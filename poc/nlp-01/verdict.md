# Verdict NLP-01

## GO

ACE 0.9.34 avec ERG 2018 fournit les données nécessaires pour exploiter ses
analyses grammaticales HPSG :

- tokens initiaux et internes, avec identifiants, positions, formes, POS et
  probabilités disponibles ;
- nombre de lectures rendues, dans la limite configurée ;
- dérivation HPSG brute et décodée en arbre ;
- arbre syntaxique de constituants brut et décodé ;
- traits morphosyntaxiques instanciés, notamment `SF`, `TENSE`, `MOOD`, `PROG`,
  `PERF`, `PERS`, `NUM` et `IND` ;
- rang de retour, score ACE et probabilité de chaque analyse ;
- tailles du chart, notes, avertissements et erreurs ;
- échec d'analyse explicite avec zéro lecture et aucune analyse fabriquée.

Sur les dix fixtures, les neuf constructions grammaticales ou fragmentaires
ont produit des analyses. La phrase non grammaticale a produit zéro lecture.
Le cas de négation a atteint la limite configurée de dix résultats : son nombre
total de lectures n'est donc pas établi par cette exécution.

## Limite

La dérivation exportée ne contient pas l'AVM complète de chaque nœud de phrase.
ACE expose l'arbre de règles, les entrées lexicales, les scores, les spans et
les traits de tokens ; d'autres traits grammaticaux sont observables dans la
MRS. Une représentation exigeant toutes les structures de traits HPSG internes
nécessiterait une instrumentation supplémentaire. L'adaptateur ne devra pas
inventer les traits absents.

Le rang est l'ordre retourné par ACE et ne constitue pas un identifiant stable
entre versions d'ACE ou d'ERG.
