# HYP-08 — Stockage froid et pruning réversible

Douze hypothèses sont classées hot, warm ou cold selon support, contradiction,
récence, redondance et coût. Les observations et justifications immuables restent
en Parquet ; seules les structures dérivées des hypothèses froides quittent
l'index actif. Un manifeste décrit l'archive Zstandard. H09 est ensuite réactivée
à partir des données canoniques et comparée à son hash antérieur au pruning.

```bash
./poc/hyp-08/run.sh
```
