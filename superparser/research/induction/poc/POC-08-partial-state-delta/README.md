# POC-08 — États rapportés et différentiel partiel

## État

`GO` formel borné sur les 849 observations réelles — v0.2.

`PartialState` ne contient que les contraintes explicitement observées d'une
source à un temps relatif. `compare_partial_states` distingue ajout, maintien,
renversement explicite et absence de mention. Il refuse de fusionner deux
sources ou un ordre temporel inversé. Le benchmark emploie exclusivement les
contraintes de référence du cache réel.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q \
  superparser/tests/test_partial_state.py

PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-08-partial-state-delta/implementation/benchmark.py
```

