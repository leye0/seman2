# Protocole

Le benchmark dérive 2 633 épisodes des 849 observations. Les observations
0–599 donnent 1 826 épisodes d'entraînement et 725–848 donnent 398 épisodes de
test. Les positions d'arguments proviennent des mentions de la phrase courante.

Les événements niés ou hypothétiques sont exclus. Un effet impliquant un
référent absent des arguments n'est pas généralisé. Les absences restent
inconnues, les polarités opposées sont des contre-exemples, et une évolution
également fréquente après d'autres événements échoue au seuil de lift.

Critères : précision held-out ≥ 0,50 et avantage F1 strict sur les baselines
fréquentielle et syntaxique. Une amélioration minuscule ne suffit pas.

