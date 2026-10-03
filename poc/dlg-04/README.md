# DLG-04 — Import ISO 24617-2 / DiAML sans perte

Le POC importe les trois dialogues TRAINS publiés par DialogBank. Il conserve
deux vues complémentaires : l'arbre XML générique complet pour l'aller-retour,
et une vue attribuée explicitant tokens, segments fonctionnels, actes,
dimensions, fonctions, participants, qualificateurs et dépendances.

Les ressources restent dans `.local/share/dialogbank` et ne sont pas recopiées
dans le POC. Pour les récupérer depuis les liens officiels :

```bash
mkdir -p .local/share/dialogbank
for n in 1 2 3; do
  curl -fL -o ".local/share/dialogbank/trains${n}.diaml" \
    "https://dialogbank.lsv.uni-saarland.de/wp-content/uploads/2022/04/trains${n}.diaml"
done
./poc/dlg-04/run.sh
```

`output/results.json` contient les empreintes SHA-256 et URL de chaque source.
Le POC importe des annotations de référence ; il ne prétend pas les prédire.
