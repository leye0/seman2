# POC-09 — Induction de transformations

## État

`GO` contrôlé / `NO-GO` sur les 849 observations réelles — v0.2.

Le moteur apprend des effets relationnels liés aux positions d'arguments d'un
composant événementiel. Il conserve support, contre-exemples, couverture,
lift face aux événements de contrôle et chaîne de preuve. Aucun rôle comme
`giver`, `recipient` ou `ownership` n'est codé. Les épisodes sont dérivés
uniquement des événements et contraintes référentielles du cache compact.
Un second benchmark temporaire utilise des suites de phrases contrôlées,
explicitement séparées des résultats réels.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q \
  superparser/tests/test_transitions.py

PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-09-transition-induction/implementation/benchmark.py

PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-09-transition-induction/implementation/controlled_benchmark.py
```

