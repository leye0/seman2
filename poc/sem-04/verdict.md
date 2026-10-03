# Verdict SEM-04

**PARTIEL — n-best réel, mais contrat incomplet.**

Phonetisaurus s'entraîne localement et produit plusieurs prononciations pour
chaque mot tenu à l'écart, y compris formes atypiques. Le modèle est un WFST
sérialisé et l'expérience conserve temps, mémoire, corpus joint et partition.

L'API Python 0.3.0 ne restitue toutefois que `(mot, phonèmes)` : ni coût, ni
alignement par candidat, ni lattice de décodage par mot. Le modèle ne doit donc
pas entrer dans le chemin principal sous ce contrat. Une adaptation directe de
la CLI/OpenFst ou une autre baseline est requise avant GO complet. Epitran reste
plus simple pour une transcription attribuée unique ; Phonetisaurus apporte le
n-best entraînable mais pas encore toute l'explicabilité exigée.
