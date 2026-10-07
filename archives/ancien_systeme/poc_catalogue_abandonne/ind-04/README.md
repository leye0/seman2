# IND-04 — Transformations récurrentes

Dix couples avant/après sont différenciés sous bindings connus puis
canonicalisés sans leurs IDs concrets. Le transform gagnant crée un nœud,
supprime une arête et en ajoute deux. Il est réappliqué, contrôlé par Z3 et
comparé aux graphes attendus par NetworkX et rustworkx.

Une seconde induction consomme les deltas ISU effectivement produits par
DLG-07. Elle abstrait les transitions d'acceptation et de contestation en une
même transformation anonyme : changer le statut d'un fait existant et ajouter
l'acteur qui justifie cette transition. Les deltas sources, leurs inverses et
les étapes qui ne correspondent pas restent tous accessibles.

```bash
./poc/ind-04/run.sh
```
