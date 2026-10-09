# POC-06 — Catégories latentes de référents

## État

`GO` borné pour les familles de compatibilité réelles v0.2.

## Hypothèse

Les populations de référents observées aux ports de composants permettent de
découvrir des familles plus prédictives que la seule catégorie grammaticale.

## Périmètre v0.1

- signatures binaires `(composant, port)` par référent opaque ;
- clustering complete-link des ports selon leur support de substitution ;
- appartenance multiple et familles spécialisées reliées à un parent ;
- prédiction des référents compatibles avec un port tenu à l'écart ;
- abstention sur un port inconnu ;
- sélection des seuils sur validation et évaluation chronologique held-out.

Les seules données sont les 849 observations compactes de *The Map of
Everything*. Une substitution relie un lemme nominal opaque à la règle parente
et à sa position d'enfant.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q \
  superparser/tests/test_latent_referents.py

PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-06-latent-referent-classes/implementation/benchmark.py
```

