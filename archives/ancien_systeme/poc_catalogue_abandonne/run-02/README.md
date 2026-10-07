# RUN-02 — Checkpoint coordonné et reprise équivalente

Cette POC repart du checkpoint de RUN-01, vérifie les empreintes et la copie
SQLite cohérente, lance un nouveau noyau Soar, recharge l'agent, reconstruit la
working memory depuis l'Active Context et compare les décisions avant/après.

Elle restaure aussi la session d'ingestion cognitive arrêtée à mi-source dans
un nouveau runtime, traite le record restant, puis compare le snapshot complet
à une exécution ininterrompue des deux mêmes records. L'équivalence porte donc
sur l'Artifact Arena, les résidences/activations, le Control State, le scheduler
et le curseur d'entrée — pas seulement sur un compteur final.

Elle vérifie aussi qu'une altération du contexte ou de la base change son
empreinte, que la corruption du checkpoint cognitif est effectivement refusée,
et qu'un changement de l'ordre des records source empêche la reprise.

```bash
./poc/run-02/run.sh
```
