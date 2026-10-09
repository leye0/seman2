# Analyse

## Résultats

Le manifeste contient trois généralisations positives avec transfert lexical
tenu à l'écart et un contraste de polarité négatif.

- reconstruction exacte : **100 %** des candidats produits ;
- attentes par cas : **4/4 (100 %)** ;
- latence médiane de proposition : **95,708 ms** ;
- p95 historique : **1 473,428 ms** avant le passage à une racine sélectionnée ;
- pic d'allocations : **6,315 MB** ;
- contraste affirmatif/négatif : **0 candidat**, comme attendu.

La représentation compacte v0.2 supprime désormais le produit cartésien des
racines : chaque observation expose au plus une analyse sélectionnée.

## Variables

Les variables conceptuelles et les substitutions résiduelles sont séparées.
Les spans deviennent toujours des résidus : deux exemples de même longueur ne
doivent pas transformer leurs positions accidentellement égales en contrainte
du composant.

La mémoïsation des paires de valeurs produit la liaison classique :
`f(a,a)` et `f(b,b)` donnent `f(X,X)`. Deux variables distinctes peuvent
cependant recevoir la même valeur sur une nouvelle observation ; aucune
contrainte de différence n'est inventée.

## Compression

Les gains estimés du meilleur candidat sont négatifs sur deux observations
(`-188` à `-251` octets). C'est normal : le coût du gabarit et de ses bindings
n'est pas amorti sur seulement deux exemples. Aucune conclusion MDL n'est
tirée avant le POC-03.

## Limite assumée

L'opérateur exige la même topologie et les mêmes règles grammaticales. Il ne
doit donc pas rapprocher actif/passif, adjonctions ou sous-graphes de tailles
différentes. Cette restriction évite de déguiser le matching approximatif du
POC-05 en anti-unification exacte.

