# HYP-04 — Evidence Ledger et ranking contextuel

Un ledger immuable combine évidence directe/contextuelle, phonologique,
sémantique, discursive, outcomes, contradictions, provenance, récence et coût
descriptif. Polars/NumPy calculent les contributions et DuckDB les agrège par
famille pour trois contextes.

Chaque entrée référence aussi l'identifiant cognitif HYP-01 de son hypothèse et
les supports minimaux réellement calculés par HYP-02. L'empreinte du résultat
HYP-02 est conservée : le ranking n'opère plus sur quatre labels orphelins.

```bash
./poc/hyp-04/run.sh
```
