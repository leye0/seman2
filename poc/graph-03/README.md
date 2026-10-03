# GRAPH-03 — Données pour l'ambiguïté

Le POC construit des groupes factorisés à partir de candidats réels ERG,
Link Grammar, Allen, Temporal DRT/SDRT, Duckling et Phonetisaurus. Il ajoute les
annotations compatibles DiAML, une paire croisée SDRT, un arbre RST et le bundle
ERG/Dynamic Syntax sans les confondre avec des alternatives exclusives. La
future interface ISU est une fixture explicitement attribuée comme telle.

Les payloads complets sont dans `candidate-payloads.parquet`. Le graphe ne crée
ni sélection, ni conflit entre familles, ni nœud représentant le produit
cartésien des groupes.

Chaque groupe porte maintenant un sélecteur exact dans l'artefact source. Le
support enregistre la liste des empreintes de ses candidats et le test exige
qu'elle corresponde exactement aux payloads reliés ; aucun lien vers une
simple « sortie représentative » d'une autre fixture n'est accepté.

```bash
./poc/graph-03/run.sh
```
