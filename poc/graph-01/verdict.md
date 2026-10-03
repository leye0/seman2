# Verdict GRAPH-01

**GO pour le contrat ; couverture mesurée encore partielle.**

NetworkX conserve identités, arêtes parallèles, ordre et relations ; Parquet
conserve les tables interopérables ; le JSON canonique attribué conserve les
structures propres aux analyseurs. Les trois représentations passent un
aller-retour. Les limites sont explicites : un graphe tabulaire ne représente
pas directement les arbres/objets arbitraires ni les octets source, qui restent
donc des payloads ou artefacts adressés par chemin et empreinte.

La matrice couvre chaque POC planifiée, mais SEM-05 et DLG-06 à DLG-14 ne sont
encore que des fixtures contractuelles. Le verdict ne devient donc pas une
validation d'intégration finale avant leur exécution et un nouveau passage de
GRAPH-01.
