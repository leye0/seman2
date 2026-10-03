# HYP-02 — Justifications, dépendances et contradictions

Le POC construit un DAG de supports partagés pour H1 à H4, rejette un cycle,
énumère avec Z3 tous les ensembles non vides compatibles, extrait les modèles
maximaux et relie un `unsat core` aux hypothèses demandées. Il compare les
nœuds/arêtes uniques avec quatre copies naïves des explications.

```bash
./poc/hyp-02/run.sh
```
