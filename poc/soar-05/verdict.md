# Verdict SOAR-05

`GO_REAL_SML_DUCKDB_RETRIEVAL_BRIDGE` : le protocole output-command → requête
DuckDB → injection WME → consommation Soar → retrait WME fonctionne réellement.
Le dépôt persistant n'est jamais copié en bloc et une alternative hors beam est
réactivée à la demande avec la même provenance RET-03.
