# Verdict SEM-03

**GO — transformations pondérées intégrées, sérialisables et composables.**

Les fixtures couvrent segmentation, candidat phonographique, rébus, élision,
ponctuation, translittération et distracteur sans chemin. `io` conserve deux
sorties concurrentes. La composition vers `input/output` additionne les coûts
dans le semi-anneau tropical et conserve les règles participantes.

Chaque analyse possède une ascendance causale Source/Observation, et le FST
ainsi que sa vraie table de symboles survivent à une sérialisation/relecture.
Aucun résultat ne remplace la source et aucun chemin n'implique une synonymie
ou une correction canonique.
