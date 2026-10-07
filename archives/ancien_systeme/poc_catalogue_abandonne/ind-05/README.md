# IND-05 — Promotion, merge, split et oubli

Six patterns contrôlés produisent des métriques DuckDB/Polars/NumPy/SciPy et
structurelles séparées : support, compression, récurrence, gain prédictif, coût,
exceptions et stabilité. Une politique explicite rend et justifie promotion,
fusion, séparation, oubli ou maintien sans muter le Learned Graph.

La politique évalue aussi les vrais patterns IND-03/04. Comme ils ne disposent
encore que de quatre graphes et cinq transitions, sans outcome réservé ni
fenêtres temporelles suffisantes, elle publie les métriques disponibles et les
lacunes puis les conserve comme candidats. Promotion, fusion et oubli sont
explicitement interdits à ce stade; les deux types structurels incompatibles ne
sont pas fusionnés par commodité.

```bash
./poc/ind-05/run.sh
```
