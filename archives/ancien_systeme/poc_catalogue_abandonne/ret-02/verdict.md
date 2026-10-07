# Verdict RET-02

**GO — top-k partiel explicable et contraint.**

La forme complète précède la forme partielle, qui précède le distracteur. Le
contexte absent est explicitement retourné, le bruit est filtré sur disque et
les bindings satisfont les contraintes injectives et typées vérifiées par Z3.

Sur GRAPH-03, les 40 candidats passent la présélection, toutes leurs empreintes
se résolvent dans le support attribué et les candidats sans conflit signalent
exactement le nœud et l'arête optionnels manquants. La forme complète précède
la forme partielle sans effacer cette dernière.
