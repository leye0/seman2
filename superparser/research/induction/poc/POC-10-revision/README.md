# POC-10 — Révision et lignée d'hypothèses

## État

`GO` contrôlé / audit réel sans occasion de réfutation — v0.1.

Le registre conserve des versions immuables, chaque preuve et contre-exemple,
la fiabilité de source, la retraite d'un parent et les spécialisations encore
soutenues. Les données brutes ne sont jamais supprimées.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q superparser/tests/test_revision.py
PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-10-revision/implementation/benchmark.py
```

