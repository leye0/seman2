# RUN-01 — Graphe durable et ingestion cognitive complète sur données réelles

Cette POC lit de vrais Parquet canoniques avec une mémoire bornée, exécute
ACE/ERG et Dynamic Syntax, conserve les succès et échecs, adapte neuf MRS,
construit les candidats temporels et hypothèses, puis les fait traverser état,
épisode, retrieval, beam et une session Soar réelle.

En parallèle, elle ingère directement un extrait réel de
`data/the_map_of_everything_nlp_novel.txt` dans le cœur cognitif RAM-first. Les
28 modules requis — analyses formelles, sémantique, temps, contraintes,
hypothèses, Soar, discours, dialogue, épisodes, retrieval, statistiques,
induction, culture et transformations — doivent tous participer. La preuve ne
se limite pas à leur présence dans une trace : l'état terminal de consolidation
doit avoir leurs productions dans son ascendance causale jusqu'au record source.

La session est arrêtée après le premier de deux records, sans tâche pendante,
puis son arène d'artefacts, son scheduler, son Control State et son curseur de
source sont écrits atomiquement pour RUN-02.

Chaque résultat devient un artefact SQLite append-only avec parents, epoch,
empreinte, clé d'idempotence et événement durable. Le store refuse un parent
absent, une frontière non déclarée ou un retry contradictoire.

```bash
./poc/run-01/run.sh
```

La POC ne lit aucune sortie d'une POC plus basse. Elle appelle directement les
services et ressources du runtime ; les dossiers de POC ne servent jamais de
bus cognitif.
