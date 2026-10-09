# Protocole

## Données communes

Le benchmark charge et valide les **849** `ObservationGraph` compacts réels. Il
importe ensuite les mesures persistées des POC-06 à POC-12 et vérifie que leur
audit réel porte lui aussi sur exactement 849 observations.

Les architectures A, B et C reçoivent une copie identique de ce vecteur. Elles
partagent les onze primitives existantes : aucune annotation, règle ou mesure
supplémentaire n'est accordée à un candidat.

## Comparaison

Les différences mesurées sont exclusivement topologiques : nombre de moteurs,
dépendances traversant une frontière, services communs, primitives dupliquées
et rayon maximal d'un échec réel. Les échecs constatés sont ceux de POC-07
(`relations`) et POC-09 (`transitions`).

## Données contrôlées

Conformément à la règle applicable à partir de POC-09, les quatre ablations
emploient temporairement des données contrôlées. Elles sont publiées séparément
de l'audit réel et ne changent aucun score du roman.

## Critère

Le POC passe si les trois candidats ont exactement les mêmes preuves, si tous
les audits réels annoncés contiennent 849 observations, si aucune primitive
n'est copiée entre moteurs et si la règle de décision reproductible choisit B.
