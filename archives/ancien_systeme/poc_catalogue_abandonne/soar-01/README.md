# SOAR-01 — Working memory et contexte actif

Le POC crée réellement les WMEs via SML pour graphe, variable, contrainte,
hypothèses, justifications, structure récupérée, but et provenance. Seules H1/H2
du beam entrent dans Soar ; H3/H4 restent dans le Parquet persistant. Deux
productions et deux cycles montrent la lecture et la modification du choix.

La POC inspecte aussi le checkpoint cognitif vérifié de RUN-01. Elle confirme
que le worker Soar réel a reçu, pour chaque hypothèse active, ses références
sémantique, temporelle, référentielle, de contraintes, d'observation et de
justification; que toutes sont dans l'ascendance bottom-up; et qu'aucune
alternative inactive ni dépôt persistant complet n'a été copié dans la WM.

```bash
./poc/soar-01/run.sh
```
