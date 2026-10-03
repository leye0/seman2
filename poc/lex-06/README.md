# LEX-06 — SUMO et mappings WordNet

Cette POC établit les structures ontologiques externes accessibles depuis un
synset WordNet 3.0 : mappings typés vers SUMO, concepts visés, relations
directes et axiomes SUO-KIF qui mentionnent ces concepts.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-06/run.sh
```

Le script régénère :

- `output/results.json`, les cinq fixtures, mappings et axiomes structurés ;
- `output/corpus-inventory.json`, l'inventaire des mappings, opérateurs, clés
  manquantes et symboles KIF ;
- `output/resource-vs-inference.json`, la frontière entre lookup, intégration
  ontologique et raisonnement ;
- `output/raw/selected-mapping-lines.json` et
  `output/raw/selected-kif-axioms.json`, les données natives retenues ;
- `output/summary.json` et `output/versions-and-parameters.json`.

## Résultat

**ADAPTATEUR À DÉVELOPPER, RESSOURCE ET LOOKUP DIRECT VALIDÉS.** Les quatre
fichiers WordNet–SUMO couvrent 117 658 des 117 659 synsets WordNet 3.0. Ils
contiennent 115 951 clés effectivement mappées vers SUMO. Les 68 fichiers KIF
de production fournissent 189 087 formules directement indexables.

Les fixtures couvrent :

- l'équivalence `dog.n.01 → DomesticDog=` ;
- la subsomption `choke.v.01 → Breathing+` ;
- l'instance `hegira.n.01 → Escaping@` ;
- une entrée présente sans mapping pour `acroscopic.a.01` ;
- un synset entièrement absent des fichiers, `curdle.v.03`.

L'adaptateur de POC lit les formats, conserve la provenance et retrouve les
formules mentionnant exactement le symbole SUMO. Il n'exécute aucun théorème,
ne matérialise aucune relation transitive et ne transforme pas SUMO en
ontologie cognitive interne.

Voir `verdict.md` pour les résultats détaillés et limites.
