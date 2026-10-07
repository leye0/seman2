# HYP-06 — Partage structurel et déduplication

Le POC ingère progressivement 1 000 occurrences appartenant à trois structures
incompatibles. Les prototypes sont séparés des détails compressés et d'un index
de postings. DuckDB calcule les agrégats et permet l'accès aléatoire ; trois
épisodes sont reconstruits et comparés à leur forme développée originale.

Le test de croissance reste l'oracle contrôlé. La frontière intégrée consomme
ensuite le DAG de justifications réellement produit par HYP-02 et le ledger de
HYP-04 : ses onze nœuds sont stockés une seule fois dans Parquet, les quatre
hypothèses les référencent par postings, et leurs dix-sept instances naïves se
reconstruisent exactement. Les treize entrées du ledger doivent résoudre vers
les mêmes supports partagés et les mêmes identifiants d'artefacts cognitifs.

```bash
./poc/hyp-06/run.sh
```
