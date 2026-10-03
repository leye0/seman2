# Verdict HYP-05

**GO — le chemin factorisé ne matérialise que les compositions demandées.**

Les solutions Z3 retournées appartiennent toutes à l'ensemble valide de la
baseline. Aucune combinaison non demandée n'est créée. Les mesures mémoire sont
explicitement limitées aux allocations Python de `tracemalloc` et n'incluent
pas la mémoire native interne de Z3.
