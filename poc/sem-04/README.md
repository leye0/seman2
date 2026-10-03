# SEM-04 — G2P entraînable et candidats multiples

Entraîne Phonetisaurus 0.3.0 sur une partition reproductible de CMUdict et
demande cinq candidats pour six mots strictement tenus à l'écart.

```bash
./poc/sem-04/run.sh
```

Le modèle WFST, le corpus joint et le lexique d'entraînement sont conservés.
Le POC mesure temps, mémoire et taille du modèle, puis distingue les capacités
réelles des données que l'API Python n'expose pas.
