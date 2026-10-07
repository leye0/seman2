# DLG-06 — KoS/TTR minimal et Dialogue Gameboard

Construit un contexte public typé avec participants, moves, faits proposés,
QUD, obligations et contenus en attente. Chaque objet conserve source, statut,
alternatives et champs non résolus. Le schéma, les références et le graphe de
dépendances sont validés ; la frontière avec les croyances privées est explicite.

Deux adaptateurs intégrés consomment ensuite les sorties réelles plus basses.
La topologie conversationnelle DLG-01 devient participants et tours observés,
sans lui inventer de faits ni de QUD. Le bundle DLG-03 devient un contenu public
en attente dont les analyses ERG et Dynamic Syntax restent deux alternatives
attribuées, reliées à la même observation et explicitement non fusionnées.

```bash
./poc/dlg-06/run.sh
```
