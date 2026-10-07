# DISC-01 — Sortie IsaNLP RST

`run.sh` exécute le modèle dans un service utilisateur transitoire borné :
3 Gio de mémoire sans swap, un cœur CPU, 128 tâches et 360 secondes. Le
groupe de processus entier est arrêté en cas de dépassement. Le cache
Hugging Face installé est utilisé hors ligne afin qu'un problème réseau ne
puisse pas bloquer l'audit ni multiplier les processus.

Inspecte la sortie réelle du modèle `gumrrg` sur textes anglais/français,
courts, longs, ambigus et multi-tours, plus une entrée vide adversariale.

```bash
./poc/disc-01/run.sh
```

Le POC conserve l'arbre natif sérialisé, EDUs, spans, relations, nuclearités,
scores lorsqu'émis, latences et échecs.

Le modèle natif accepte l'entrée vide comme une EDU élémentaire vide.
L'adaptateur la rejette donc avant l'inférence avec un statut `invalid_input`
explicite ; elle n'est jamais requalifiée en analyse réussie.
