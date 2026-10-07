# Verdict SEM-04

**GO — G2P entraîné, n-best scoré, aligné et intégré.**

Phonetisaurus s'entraîne localement et produit plusieurs prononciations pour
chaque mot tenu à l'écart, y compris formes atypiques. Le modèle est un WFST
sérialisé et l'expérience conserve temps, mémoire, corpus joint et partition.

L'enveloppe Python masque les coûts, mais le décodeur natif les expose et peut
écrire ses lattices. Leur lecture OpenFst permet de retrouver pour chaque
candidat son meilleur chemin et ses groupes d'alignement. Les six observations
produisent des artefacts causalement reliés à leur Source/Observation, sans
réécriture ni sélection. Epitran reste la transcription attribuée simple,
SEM-03 les règles explicites, et Phonetisaurus fournit ici l'alternative apprise
et n-best.
