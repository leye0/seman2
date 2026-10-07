# HYP-02 — Justifications, dépendances et contradictions

Le POC construit un DAG de supports partagés pour H1 à H4, rejette un cycle,
énumère avec Z3 tous les ensembles non vides compatibles, extrait les modèles
maximaux et relie un `unsat core` aux hypothèses demandées. Il compare les
nœuds/arêtes uniques avec quatre copies naïves des explications.

H1 à H4 référencent maintenant les vrais identifiants cognitifs publiés par
HYP-01, dont les résultats et le résumé sont authentifiés par SHA-256.
NetworkX et rustworkx reconstruisent séparément le DAG et détectent le même
cycle interdit.

```bash
./poc/hyp-02/run.sh
```
