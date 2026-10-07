# Verdict CODE-02

**GO — les arbres partiels conservent tout le matériau source.**

Chaque fixture invalide expose au moins un nœud `ERROR` ou `MISSING`. Les zones
hors feuilles restent listées, notamment espaces et résidus, mais la racine et
l'observation brute permettent toujours une reconstruction exacte. Aucun échec
de parsing ne supprime silencieusement le texte.
