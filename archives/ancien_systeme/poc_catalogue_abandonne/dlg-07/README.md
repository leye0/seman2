# DLG-07 — Candidats Information State Update

Six actes couvrent assertion ambiguë, question, réponse, acceptation, rejet et
non-compréhension. Chaque candidat expose règle, préconditions, supports,
bindings, effets et cohérence Z3. Le choix peut rester nul. Chaque delta retenu
est appliqué puis inversé et doit restituer exactement l'état antérieur.

La frontière intégrée consomme aussi le contenu formel en attente réellement
émis par DLG-06. Elle construit un candidat ISU pour l'analyse ERG et un pour
l'analyse Dynamic Syntax, conserve leurs références et leur observation source,
mais n'en sélectionne aucun tant que leur correspondance sémantique reste non
résolue. L'état public demeure alors strictement inchangé.

```bash
./poc/dlg-07/run.sh
```
