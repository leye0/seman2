# HYP-07 — Beam borné avec diversité structurelle

Le POC compare un top‑k scalaire, un greedy diversifié par distance de Jaccard
structurelle et un oracle post-contexte sur 30 hypothèses déséquilibrées. Les
20 quasi-doublons lexicaux dominent le score initial; la famille temporelle
moins bien classée devient correcte après révélation du contexte.

```bash
./poc/hyp-07/run.sh
```

Seul le beam diversifié de taille 4 est injecté dans un vrai agent Soar. Il est
ensuite retiré, tandis que le Parquet conserve toutes les alternatives; une
hypothèse écartée est récupérée par DuckDB puis réactivée dans Soar.

Le trajet intégré charge également les quatre hypothèses cognitives de HYP-04,
leurs fermetures de justifications partagées de HYP-06 et la reconstruction
bit-exacte de `hyp:H4` depuis le stockage froid HYP-08. Un signal de contexte
explicite réactive H4, un beam de taille 3 conserve ses identifiants cognitifs et
ses références partagées, puis un second vrai agent Soar prend une décision
opérationnelle explicitement distincte d'une sélection de vérité.
