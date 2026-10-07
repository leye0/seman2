# LEX-05 — SemLink 2

Cette POC vérifie les correspondances réellement fournies par SemLink 2 entre
PropBank, VerbNet et FrameNet, puis suit les clés WordNet portées par les
membres VerbNet. Elle contrôle séparément les tables lexicales, les annotations
d'occurrences, les mappings de rôles et leur compatibilité avec les ressources
NLTK installées.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-05/run.sh
```

Le script régénère :

- `output/results.json`, les cinq fixtures et leurs chaînes de liens typés ;
- `output/join-rates.json`, les taux de jointure calculés avec Polars ;
- `output/corpus-inventory.json`, l'inventaire des champs, marqueurs et clés ;
- `output/resource-vs-inference.json`, la frontière entre mappings stockés et
  décision sur une nouvelle occurrence ;
- `output/raw/selected-instance-lines.json` et
  `output/raw/selected-mappings.json`, les données SemLink natives retenues ;
- `output/summary.json` et `output/versions-and-parameters.json`.

## Résultat

**PARTIEL à cause d'un écart de versions local.** SemLink 2 cible VerbNet 3.3,
Unified PropBank et FrameNet 1.7. L'installation NLTK contient VerbNet 2.1,
PropBank 1.0 et FrameNet 1.7. FrameNet s'aligne donc presque entièrement,
tandis que de nombreuses clés PropBank et VerbNet ne peuvent pas être résolues
contre les versions locales.

SemLink reste directement exploitable comme ressource autonome : 148 653
instances, 5 279 liens PropBank→VerbNet, 2 385 liens VerbNet→FrameNet et
111 258 liens d'arguments PropBank→rôles VerbNet sont lisibles. Les clés non
résolues sont conservées, jamais supprimées ou remplacées silencieusement.

WordNet n'est pas une colonne directe des tables SemLink 2. La POC suit le
chemin SemLink → membre VerbNet installé → clé de sens WordNet → synset, en
signalant cette provenance indirecte.

Voir `verdict.md` pour les taux, exemples et implications architecturales.
