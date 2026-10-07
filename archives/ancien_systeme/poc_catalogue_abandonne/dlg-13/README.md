# DLG-13 — Frontière ConvoKit/OpenDial

Un même dialogue de cinq tours est chargé dans ConvoKit pour sa topologie et
ses statistiques, puis adapté en observations primitives. Le DGB/ISU interne
est construit séparément et testé contre toute fuite de types runtime ConvoKit.
OpenDial reste non exécuté : aucune comparaison de politique fermée ne le
justifie dans ce POC.

La frontière est aussi vérifiée sur les sorties exécutées : la topologie et les
statistiques ConvoKit de DLG-12 restent une vue auxiliaire en lecture seule,
tandis que DLG-06 demeure propriétaire du DGB et DLG-07 des candidats ISU.
Aucun objet utilitaire n'est copié, et la topologie n'est jamais substituée à
l'état public ou à une théorie du dialogue.

```bash
./poc/dlg-13/run.sh
```
