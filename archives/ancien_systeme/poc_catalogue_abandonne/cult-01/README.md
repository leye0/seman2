# CULT-01 — Patterns de haut niveau sur conversations humaines

Le POC parcourt les 122 646 tours des 1 155 conversations humaines Switchboard.
Son trajet principal extrait directement du texte brut des traits lexicaux
hachés et structurels, apprend douze états de tour sans supervision, puis induit
des attentes à trois tours sur 80 % des conversations. Elles sont testées sur
des conversations disjointes et chaque support ou exception retourne aux IDs,
textes bruts et lignes sources.

Un second trajet conserve les tags SWDA hachés comme baseline annotée. Le hash
ne rend pas cette taxonomie émergente : elle est désormais nommée et rapportée
explicitement comme telle, sans entrer dans l'apprentissage du trajet brut.

```bash
./poc/cult-01/run.sh
```

Les états appris restent anonymes et propres au corpus. Le résultat démontre
des attentes discursives locales, pas encore une théorie générale de la culture.
