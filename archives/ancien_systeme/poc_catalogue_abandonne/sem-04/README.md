# SEM-04 — G2P entraînable et candidats multiples

Entraîne Phonetisaurus sur une partition reproductible de CMUdict et demande
cinq candidats pour six mots strictement tenus à l'écart. Le décodage direct
`phonetisaurus-g2pfst` conserve les coûts tropicaux, les alignements
graphèmes/phonèmes et le lattice OpenFst de chaque mot.

```bash
./poc/sem-04/run.sh
```

Le modèle WFST, le corpus joint, le lexique d'entraînement et les lattices sont
conservés. Chaque mot traverse aussi le contrat cognitif
`Source → Observation → g2p-candidate-analysis`; aucune prononciation n'est
sélectionnée et la forme observée n'est jamais réécrite.
