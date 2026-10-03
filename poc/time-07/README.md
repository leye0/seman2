# TIME-07 — Ambiguïté et révision temporelles non destructives

Cette POC conserve deux antécédents temporels concurrents, un ledger append-only
et deux événements de sélection. Une correction tardive inverse le classement
sans modifier l'observation, les hypothèses ni le snapshot de `t1`.

```bash
./poc/time-07/run.sh
```
