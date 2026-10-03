# GRAPH-02 — Contrat d'annotation externe

Le POC adapte un échantillon de chacune des familles analytiques déjà exécutées
vers `seman2.graph.v1.ExternalAnnotation`. Le contrat existe sous forme
Protobuf et Arrow/Parquet et exige provenance, version, paramètres/modèle,
formalisme, type, valeur brute structurée, spans, alternatives, contraintes et
score optionnel.

Toute analyse ici est dérivée d'une observation textuelle. Le contrat porte donc
simultanément `input_modality = text`, `derived_from_text = true` et
`is_audio_observation = false`.

Les bundles multi-producteurs sont en plus éclatés en enregistrements propres à
HeidelTime, Duckling, ACE/ERG, Dynamic Syntax, Epitran et Flite. Chaque record
porte un `source_selector` précis. Un outil qui n'a produit qu'un échec de
chargement, comme DyLan dans DLG-02, est listé comme indisponible et n'est pas
déguisé en annotation réussie. La couverture devra être rejouée lorsque de
nouveaux POC analytiques seront ajoutés.

```bash
./poc/graph-02/run.sh
```
