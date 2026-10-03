# RUN-01 — Graphe runtime durable sur données réelles

Cette POC lit de vrais Parquet canoniques avec une mémoire bornée, exécute
ACE/ERG et Dynamic Syntax, conserve les succès et échecs, adapte neuf MRS,
construit les candidats temporels et hypothèses, puis les fait traverser état,
épisode, retrieval, beam et une session Soar réelle.

Chaque résultat devient un artefact SQLite append-only avec parents, epoch,
empreinte, clé d'idempotence et événement durable. Le store refuse un parent
absent, une frontière non déclarée ou un retry contradictoire.

```bash
./poc/run-01/run.sh
```

La POC ne lit aucune sortie d'une POC plus basse. Elle appelle directement les
services et ressources du runtime.
