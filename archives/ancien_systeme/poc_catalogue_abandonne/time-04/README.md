# TIME-04 — Événements, états, aspect et persistance

Cette POC projette des fluents le long de positions relationnelles avec une
sémantique minimale inspirée de l'Event Calculus : un événement initie ou
termine une valeur et les autres fluents persistent par inertie.

```bash
./poc/time-04/run.sh
```

Elle vérifie les états intermédiaires et finaux, la persistance, l'indépendance
des fluents, l'absence de fabrication d'une valeur inconnue et le rejet de deux
effets simultanés incompatibles. Les analyses aspectuelles restent attribuées à
leur producteur.
