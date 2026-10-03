# RUN-02 — Checkpoint coordonné et reprise équivalente

Cette POC repart du checkpoint de RUN-01, vérifie les empreintes et la copie
SQLite cohérente, lance un nouveau noyau Soar, recharge l'agent, reconstruit la
working memory depuis l'Active Context et compare les décisions avant/après.

Elle vérifie aussi qu'une altération du contexte ou de la base change son
empreinte et serait donc refusée avant reprise.

```bash
./poc/run-02/run.sh
```
