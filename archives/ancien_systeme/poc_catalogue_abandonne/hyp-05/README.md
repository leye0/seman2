# HYP-05 — Composition paresseuse sans produit cartésien

Compare la matérialisation exhaustive à un encodage factorisé Z3 sur quatre
tailles, dont `3 × 4 × 3 × 2`. Trois assemblages seulement sont demandés par
cas. Le POC mesure objets, requêtes solveur, latence et allocations Python.
Chaque stratégie s'exécute aussi dans un processus frais; `ru_maxrss` mesure le
pic résident total, y compris les allocations natives de Z3. Le résultat réel
factorisé de GRAPH-03 est authentifié et contrôlé en plus des tailles
synthétiques exigées.

```bash
./poc/hyp-05/run.sh
```
