# Verdict HYP-05

**GO — le chemin factorisé ne matérialise que les compositions demandées.**

Les solutions Z3 retournées appartiennent toutes à l'ensemble valide de la
baseline et respecte tous les bindings demandés. Aucune combinaison non
demandée n'est créée. `tracemalloc` mesure les allocations Python et deux
processus frais fournissent des pics RSS comparables incluant la mémoire native
de Z3. Le graphe mesuré de GRAPH-03 confirme lui aussi zéro combinaison
cartésienne matérialisée.
