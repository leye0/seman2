# Verdict SOAR-05

`GO_REAL_SML_DUCKDB_RETRIEVAL_BRIDGE` : le protocole output-command → requête
DuckDB → injection WME → consommation Soar → retrait WME fonctionne réellement.
Le dépôt persistant n'est jamais copié en bloc et une alternative hors beam est
réactivée à la demande avec la même provenance RET-03.

Le même bridge traite maintenant une clé et des identifiants réellement produits
par l'ingestion RUN-01. Deux hypothèses sur trois entrent temporairement en WM;
la troisième reste externe et aucune sélection de vérité n'est ajoutée à la
famille cognitive.
