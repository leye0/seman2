# Verdict RET-04

**GO — la collection complète n'est pas matérialisée pour la recherche.**

Le plan DuckDB et les IDs candidats sont conservés. Moins de 1 % des fragments
de la plus grande collection sont chargés en mémoire active, puis tous sont
confirmés structurellement. Les limites de la mesure mémoire (`tracemalloc`,
allocations Python) sont complétées par `VmRSS` et `ru_maxrss`, qui incluent les
allocations natives. La même frontière présélectionne une famille mesurée de
GRAPH-03 sur statistiques étroites avant de charger et authentifier ses seuls
payloads candidats.
