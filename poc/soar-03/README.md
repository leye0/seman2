# SOAR-03 — Mémoire épisodique et sémantique

Le POC exerce les deux mémoires natives de Soar 9.6.5 via SML. Trois concepts
sémantiques liés sont ajoutés puis récupérés par activation et par une requête
d'agent. Trois épisodes partageant acteur/canal mais portant des événements
distincts sont encodés, puis parcourus par requête indicée, `next` et
`previous`.

```bash
./poc/soar-03/run.sh
```

Les identifiants LTI, activations, scores de correspondance, identifiants
d'épisode, reconstructions et statistiques natives sont archivés. Le POC rend
aussi explicite la frontière d'export : SMem fournit un export texte complet;
Epmem fournit une sauvegarde SQLite et `print`/`viz` par épisode, mais pas
d'export texte complet natif.
