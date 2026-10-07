# IND-03 — Sous-graphe récurrent anonyme

Le moteur expérimental énumère tous les sous-graphes induits connexes à trois
nœuds, les canonicalise sous tout renommage et classe leur support. Le motif
gagnant est revérifié sur dix graphes par NetworkX et rustworkx. Les bindings de
chaque occurrence, les deux exceptions et leurs sources sont conservés.

La même énumération est appliquée aux quatre sous-graphes de justification
réellement produits par HYP-02. Elle découvre, sans nom métier, le chemin
récurrent support → conclusion dérivée → hypothèse, conserve les bindings vers
chaque nœud source et laisse les motifs moins fréquents dans les statistiques
de candidats. NetworkX et rustworkx doivent encore concorder.

```bash
./poc/ind-03/run.sh
```
