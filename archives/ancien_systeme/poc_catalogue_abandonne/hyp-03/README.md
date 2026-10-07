# HYP-03 — Révision temporelle non destructive

Rejoue `io` de `t1` à `t2` avec épisodes intermédiaires, correction explicite,
liens rétrospectifs datés et ledger append-only. Le ranking DuckDB est calculé
sur le préfixe d'évidence disponible à chaque instant.

Les objets historiques et leurs identifiants cognitifs viennent de HYP-01, le
jeu de candidats/justifications vient de HYP-02 et les gagnants contextuels de
HYP-04 servent de contrôle indépendant. Les trois résultats amont sont
authentifiés par SHA-256.

```bash
./poc/hyp-03/run.sh
```
