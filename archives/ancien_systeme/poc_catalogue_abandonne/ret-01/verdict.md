# Verdict RET-01

**GO — correspondance exacte avec bindings de nœuds et d'arêtes.**

Les deux occurrences attendues sont retrouvées malgré des IDs différents. Les
attributs, directions et deux arêtes parallèles sont conservés. Le distracteur
et une requête négative ne produisent aucun faux positif.

Sur la matière intégrée, les 40 candidats GRAPH-03 sont tous retrouvés
exactement une fois avec leur groupe, support, artefact source et empreinte;
NetworkX et rustworkx s'accordent sur chaque occurrence.
