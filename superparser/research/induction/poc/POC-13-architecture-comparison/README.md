# POC-13 — Comparaison architecturale

## État

`GO` pour le choix provisoire **B — deux moteurs**, v0.1.

Les trois candidats rejouent strictement le même vecteur de résultats. Le
POC ne prétend donc pas que B apprend mieux : B est le plus petit découpage
qui isole les échecs réels des relations/transitions du chemin structural,
sans copier de primitive.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q \
  superparser/tests/test_architecture_comparison.py
PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-13-architecture-comparison/implementation/benchmark.py
```

Voir [architecture_comparison.md](architecture_comparison.md) pour la matrice,
les ablations et l'API proposée pour la passe 3.
