# X-04 — Benchmark de cohérence multi-tours

Le benchmark rejoue les huit scénarios DLG-14, puis injecte séparément dix
ruptures architecturales. Un validateur exécutable s'arrête au premier invariant
violé et rend le delta fautif ainsi que le chemin observation–décision–état.

```bash
./poc/x-04/run.sh
```
