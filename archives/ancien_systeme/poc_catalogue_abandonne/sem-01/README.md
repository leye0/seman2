# SEM-01 — Transcription phonologique attribuée et non destructive

Cette POC exécute Epitran pour le français et l'anglais, ainsi que le
`lex_lookup` de Flite pour chaque fixture anglaise. La forme écrite,
son span et son hash restent intacts ; l'IPA et les alignements sont des
analyses dérivées explicitement distinctes d'une observation acoustique.

```bash
./poc/sem-01/run.sh
```

Flite expose ici ses phones natifs CMU/ARPAbet, pas de l'IPA : le contrat le dit
explicitement et conserve séparément les candidats lookup/fallback et LTS. Les sorties
vides, partielles ou comportant des fragments non prononcés restent des états
et avertissements inspectables.
