# RUN-04 — Opérateurs Soar et transformation d'état

Cette POC poursuit RUN-03 dans son propre store. Pour chaque réponse, elle
construit trois transformations concurrentes et attribuées. Un vrai cycle
d'opérateur Soar propose les candidats, exprime une préférence et applique le
choix. Les trois conversations du corpus sont traitées dans des contextes Soar
indépendants afin que leurs opérateurs ne se retrouvent pas dans une fausse
compétition globale.

La transformation sélectionnée rattache seulement la réponse comme candidat
d'évidence. Elle ne ferme pas le QUD et n'affirme pas que la réponse est vraie
ou pertinente. L'état et l'épisode résultants sont persistés à l'époque 2 avec
leur ascendance complète.

```bash
./poc/run-04/run.sh
```

Le cas négatif couvert par les tests retire le lien de provenance : Soar entre
alors en impasse au lieu de choisir silencieusement le rattachement.
