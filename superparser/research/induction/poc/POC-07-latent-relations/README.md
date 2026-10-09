# POC-07 — Relations latentes, équivalence et contraintes

## État

`NO-GO` prédictif sur les 849 observations réelles — v0.2.

Le modèle propose, par domaine, des hypothèses `EQUIVALENT`, `INVERSE`,
`IMPLIES` et `INCOMPATIBLE` à partir d'assertions vraies, fausses explicites ou
inconnues. Chaque hypothèse conserve support, contradictions, couverture,
confiance empirique et borne calibrée de Wilson.

Il ne reçoit ni signification de lexème ni connaissance physique. Le benchmark
utilise exclusivement les contraintes de référence explicites du cache réel.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q \
  superparser/tests/test_latent_relations.py

PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-07-latent-relations/implementation/benchmark.py
```

