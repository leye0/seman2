# IND-04 — Transformations récurrentes

Dix couples avant/après sont différenciés sous bindings connus puis
canonicalisés sans leurs IDs concrets. Le transform gagnant crée un nœud,
supprime une arête et en ajoute deux. Il est réappliqué, contrôlé par Z3 et
comparé aux graphes attendus par NetworkX et rustworkx.

```bash
./poc/ind-04/run.sh
```
