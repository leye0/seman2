# TIME-02 — Algèbre d'intervalles et propagation de contraintes

Cette POC implémente les treize relations de l'algèbre d'intervalles d'Allen,
leurs converses, leur composition et une fermeture par cohérence de chemins.
Le formalisme est attribué comme analyse externe : ses noms ne deviennent pas
des primitives du Learned Graph.

La table de composition est dérivée exhaustivement par classification de
triplets d'intervalles propres sur sept extrémités ordonnées, puis sérialisée
dans `output/composition-table.json`.

## Exécution

```bash
./poc/time-02/run.sh
```

Les fixtures testent composition canonique, disjonctions conservées, réseau
partiel, égalité, raffinement et contradiction explicite.
