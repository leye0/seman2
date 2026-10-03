# CULT-01 — Patterns de haut niveau sur conversations humaines

Le POC parcourt les 122 646 tours des 1 155 conversations humaines Switchboard.
Les tags SWDA externes sont anonymisés avant induction. Des attentes à trois
tours sont apprises sur 80 % des conversations et testées sur des conversations
disjointes. Chaque support ou exception retourne aux IDs, textes bruts, lignes
sources, rôles de locuteur, sujet et fichier du corpus.

```bash
./poc/cult-01/run.sh
```

Le résultat ne prétend pas que les tags SWDA sont une ontologie culturelle : ce
sont des observations externes permettant d'éprouver l'induction de scripts.
