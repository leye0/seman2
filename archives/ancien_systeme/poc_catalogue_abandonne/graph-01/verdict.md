# Verdict GRAPH-01

**GO — racines mesurées complètes et contrat sans perte validé.**

NetworkX conserve identités, arêtes parallèles, ordre et relations ; Parquet
conserve les tables interopérables ; le JSON canonique attribué conserve les
structures propres aux analyseurs. Les trois représentations passent un
aller-retour. Les limites sont explicites : un graphe tabulaire ne représente
pas directement les arbres/objets arbitraires ni les octets source, qui restent
donc des payloads ou artefacts adressés par chemin et empreinte.

La matrice couvre désormais chaque POC planifiée par une sortie mesurée. Chaque
`results.json` complet est préservé comme payload canonique, y compris toutes
ses alternatives; les fixtures contractuelles ne servent plus qu'aux cas
structurels adversariaux. NetworkX et rustworkx s'accordent sur les nombres de
nœuds, d'arêtes et de paires parallèles avant la sérialisation Parquet.
