# POC-11 — Transfert inter-constructions

## État

`GO` contrôlé / signal réel exploratoire — v0.1.

Les alignements sont induits depuis les effets relationnels opaques et une
permutation explicite des ports. Les résidus morphosyntaxiques restent attachés
à chaque construction. Les ports jamais observés sont canonicalisés au lieu de
provoquer une explosion combinatoire.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q superparser/tests/test_cross_construction.py
PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-11-cross-construction/implementation/benchmark.py
```

