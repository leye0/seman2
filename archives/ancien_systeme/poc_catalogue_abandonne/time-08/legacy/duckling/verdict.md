# Verdict TIME-02

Duckling fournit bien les dimensions et champs structurés demandés. Son API
sérialise notamment la dimension interne `Numeral` sous le nom `number`. Les
spans sont validés par tranchage Unicode exact de la source.

La richesse des sorties impose de préserver les alternatives. Avec
`latent=true`, `42` est simultanément un nombre et un candidat latent de
monnaie, quantité et temps ; `deux heures` en français reçoit une durée et une
lecture temporelle. Ces sorties ne sont pas des doublons à supprimer sans
décision explicite.

Les intervalles ne sont pas uniformes entre langues sur les fixtures choisies :
l'anglais `from Monday to Wednesday` produit un objet temporel avec bornes,
tandis que le français produit deux points temporels. La matrice
dimension×locale expose ce comportement au lieu d'annoncer une parité de
couverture non observée.

Verdict : GO comme analyseur structuré attribué. Une intégration doit fixer la
date de référence, conserver `latent` et `values`, et laisser le moteur
cognitif décider si plusieurs analyses concurrentes doivent être classées.
