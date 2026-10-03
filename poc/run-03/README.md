# RUN-03 — Boucle question-réponse inter-époques

Cette POC exécute d'abord l'époque question de RUN-01 dans son propre store,
puis poursuit le même graphe durable. Chaque décision Soar
`retrieve-answer` résout la réponse réelle la mieux classée dans les Parquet.
La réponse devient une source de l'époque 1, repasse par les analyses vivantes,
les adaptateurs, la temporalité et les hypothèses, puis met à jour état et
épisode avant une nouvelle décision Soar `assess-answer`.

Le corps HTML brut, sa projection textuelle, son empreinte et ses coordonnées
source sont conservés. Une première unité phrastique bornée est analysée; toute
normalisation terminale est déclarée dans l'artefact d'observation.

```bash
./poc/run-03/run.sh
```

Les oracles contrôlent les deux époques, l'ascendance depuis la décision de
question, la continuité état/épisode, les trois analyses MRS et l'équivalence
des décisions après reconstruction du checkpoint.
