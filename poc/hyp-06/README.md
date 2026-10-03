# HYP-06 — Partage structurel et déduplication

Le POC ingère progressivement 1 000 occurrences appartenant à trois structures
incompatibles. Les prototypes sont séparés des détails compressés et d'un index
de postings. DuckDB calcule les agrégats et permet l'accès aléatoire ; trois
épisodes sont reconstruits et comparés à leur forme développée originale.

```bash
./poc/hyp-06/run.sh
```
