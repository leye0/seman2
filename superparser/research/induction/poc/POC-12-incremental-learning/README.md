# POC-12 — Ingestion incrémentale et consolidation

## État

`GO` sur les 849 observations réelles — v0.1.

L'index groupe les observations par signature grammaticale non lexicale,
compare uniquement les voisins, versionne les promotions/retraits et persiste
son cache. Les invalidations tardives conservent toute la lignée.

## Exécution

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q superparser/tests/test_incremental_index.py
PYTHONPATH=superparser /usr/bin/python3 \
  superparser/research/induction/poc/POC-12-incremental-learning/implementation/benchmark.py
```

