# Protocole

Le corpus réel est découpé chronologiquement : observations 0–599 pour
l'entraînement, 600–724 pour la sélection de politique et 725–848 pour le test.
Les 849 observations participent donc toutes exactement une fois.

Contrôles adversariaux :

- comparaison à `B1`, qui autorise tous les `NOUN` à chaque port ;
- port entièrement inconnu exigeant une abstention.

Critères : au moins cinq contextes de test couverts, F1 ≥ 0,10 et avantage
strict sur `B1/NOUN`. Aucun oracle sémantique externe n'est utilisé.

