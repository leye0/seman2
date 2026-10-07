# HYP-08 — Stockage froid et pruning réversible

Douze hypothèses sont classées hot, warm ou cold selon support, contradiction,
récence, redondance et coût. Les observations et justifications immuables restent
en Parquet ; seules les structures dérivées des hypothèses froides quittent
l'index actif. Un manifeste décrit l'archive Zstandard. H09 est ensuite réactivée
à partir des données canoniques et comparée à son hash antérieur au pruning.

Une seconde exécution applique ce lifecycle à la matière effective de HYP-06
et HYP-04. L'hypothèse H4 et son identifiant cognitif passent au froid; ses
références vers les nœuds partagés et les entrées du Evidence Ledger restent
dans les sources immuables. Un nouveau contexte la réactive en relisant ces
sources, puis compare bit-à-bit sa structure canonique à celle d'avant pruning.
Les hashes des deux sources sont contrôlés avant et après l'opération.

```bash
./poc/hyp-08/run.sh
```
