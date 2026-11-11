# Cas 64 — question citée coupée avant une coordination de prédicats

**Statut : non corrigé, diagnostic de dépendance contextuelle documenté.**
Ce dossier est une observation du corpus gelé, pas une nouvelle règle de
grammaire ni une preuve que le texte complet recevrait un bon arbre.

## Référence et préparation

- Cohorte historique v1 `QUOTE_BALANCED` inchangée, SHA-256 :
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- Livre 766 (*David Copperfield*), index **64**, ordinal **1968**,
  `case_id=766:bc614b374f3befb4`.
- Source : artefact `novel-parse-diagnostics-500` de l'Action
  [42665231444](https://github.com/leye0/seman2/actions/runs/42665231444),
  fichiers `context_dependency.jsonl`, `residual_research_cases.jsonl`
  et `per_sentence.jsonl`.
- Tout rejeu du cas doit utiliser `parse_corpus_case` et
  `Parser.parse`, avec le texte original et les limites habituelles.

L'unité figée commence par :

> What’s this?’ and bent his eyes upon me, as if he would have burnt me up with them.

Le relevé de provenance fournit dans **le même paragraphe**, comme phrase
précédente :

> Mr. Creakle whispered, ‘Hah!

La combinaison des deux morceaux montre le contexte potentiellement requis :

> Mr. Creakle whispered, ‘Hah! What’s this?’ and bent his eyes upon me, as if he would have burnt me up with them.

Il s'agit d'une reconstruction **de lecture contextuelle**, pas de la
nouvelle entrée canonique du benchmark. Le découpage v1 après `Hah!`
détache `and bent his eyes` de son sujet explicite `Mr. Creakle`.
`QUOTE_BALANCED` ajoute l'ouverture `‘` à l'analyse du deuxième
morceau, mais ne réinsère ni `Mr. Creakle` ni `whispered`.

## Observations mesurées

| Élément | Résultat |
| --- | --- |
| Statut canonique | `roots_without_valid_analysis` |
| Racines du résultat final de repli | 0 |
| Racines structurelles dans l'essai dialogue cadré | 1, aucune analyse complète validée |
| Candidats lexicaux | 88 |
| Mots sans candidat | 0 |
| Nœuds de forêt | 676 |
| États partiels | 23 486 |
| Dépassement forêt / k-best | Non / non |
| Analyse stricte complète | Non |
| Corpus strict | 474/500, inchangé |

Le rapport de recherche existant classe ce cas dans les pistes
`dialogue_structure` et `discourse_construction`. Les observations
permettent de soupçonner un **sujet partagé au-delà d'une coupure dans
une réplique citée**. Elles ne prouvent ni que cette seule coupure cause
tous les rejets, ni qu'une règle syntaxique précise manque.

## Suite requise avant toute correction

1. Reconstituer **sans perdre de caractères ni de spans** une unité
   prospective explicite contenant le sujet, la citation et le prédicat
   coordonné. Ne jamais remplacer les indices ou le SHA de la cohorte v1.
2. Rejouer cette unité par `extract(..., segmentation_version=2)` et
   `parse_corpus_case`, ou versionner une extension de segmentation
   si v2 ne conserve pas encore cette continuité. Ne pas créer de
   deuxième chemin public de parsing.
3. Contrôler l'arbre **de rang 1** : `Mr. Creakle` sujet de
   `whispered` **et** de `bent`, question citée rattachée à
   `whispered`, comparaison `as if ...` correctement portée.
   Relever les `rule_id`, enfants et spans source; une racine seule
   ne suffit pas.
4. Si une règle de découpage v2 doit être élargie, exiger des positifs
   indépendants et des négatifs où deux phrases sont réellement
   autonomes, avec guillemets ouverts/fermés, `!` et `?`. Préserver
   abréviations, quote-transfer et caractère non destructif du découpage.
5. Pour tout changement de grammaire, appliquer
   [GRAMMAR_CASE_FIX_PROTOCOL.md](GRAMMAR_CASE_FIX_PROTOCOL.md) :
   exemples indépendants, témoins négatifs, sensibilité du cas 359,
   qualité 120/120, contrastes 24/24 et comparaison exacte des 500
   unités avec budgets 50 000 / 500 000 inchangés.

**Aucun succès supplémentaire n'est revendiqué.** Tant que l'arbre
correct n'est pas démontré, le cas 64 reste dans la file des 26 résidus.
