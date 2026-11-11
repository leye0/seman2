# Cas 64 — question citée coupée avant une coordination de prédicats

**Statut : structure contextuelle restaurée uniquement en segmentation prospective v2 ; diagnostic grammatical non résolu.**
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

Il s'agit d'une reconstruction **de lecture contextuelle**, désormais également
vérifiée sur une véritable unité d'extraction prospective v2. Ce n'est pas la
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

## Expérience prospective v2 — 11 novembre 2026

La segmentation v2 optionnelle conserve désormais la ponctuation interne de la
citation quand **une seconde phrase entre guillemets est suivie immédiatement
d'une coordination externe** (`and`, `but` ou `or`). Sur la source
contiguë originale du roman, v1 donne **2 unités**, v2 **1 unité** ; le
round-trip de la source est exact. L'extraction brute et la variante
`QUOTE_BALANCED` gardent les mêmes caractères de provenance. Aucun
comportement de la cohorte gelée v1 n'est changé.

- [Action de validation de la source et du parseur
  42950058760](https://github.com/leye0/seman2/actions/runs/42950058760) :
  réussite, 31 tests de découpage / provenance validés.
- [Action de contre-épreuves 42950284824](https://github.com/leye0/seman2/actions/runs/42950284824) :
  réussite, 7 phrases indépendantes et 3 meilleurs arbres exportés.
- L'unité v2 réunifiée a **29 tokens**, **758 nœuds** de forêt,
  **26 147 états partiels**, calcul terminé sans saturation aux budgets
  habituels ; le parseur choisit une racine `clause_comma_sub`.
- Le sujet `Mr. Creakle`, `np_honorific_abbreviation`, est partagé par
  les deux prédicats coordonnés (`vp_coord_finite`), `whispered` et
  `bent`. C'est un gain **structurel** de contextualisation.
- L'arbre de rang 1 est **incorrect** : `upon me` est rattaché dans
  `np_pp_mod("his eyes upon me")`, au lieu du prédicat `bent`.
  Le comparatif `as if he would have burnt ...` est décomposé en
  `clause_comma_sub`, `clause_sub_front`, une
  `clause_modal_ellipsis("he would")` et une clause séparée où
  `have` est un nom (`np_bare`). L'interjection `Hah` est prise pour
  un `np_proper`.
- Les **trois meilleurs arbres** reproduisent les mauvaises familles de
  rattachements. Les sondes indépendantes démontrent notamment que
  `He bent his eyes upon me.` souffre déjà du mauvais rattachement
  de `upon me` : ce défaut n'est pas résolu par la segmentation.

**Interprétation :** présence d'un arbre complet ≠ analyse grammaticale
certifiée. Aucun nouveau succès strict n'est revendiqué : toujours
**474/500** et **26 résidus**, y compris le 64.

## Suite requise avant toute correction

1. Reconstituer **sans perdre de caractères ni de spans** une unité
   prospective explicite contenant le sujet, la citation et le prédicat
   coordonné. Ne jamais remplacer les indices ou le SHA de la cohorte v1.
2. Fait : rejouer l'unité produite par `extract(..., segmentation_version=2)`
   et `parse_corpus_case` (audit reproductible `audit_case64_context.py`).
   Toujours conserver ce seul chemin public de parsing.
3. Restant : corriger et certifier l'arbre **de rang 1** : `Mr. Creakle` sujet de
   `whispered` **et** de `bent`, question citée rattachée à
   `whispered`, comparaison `as if ...` correctement portée.
   Relever les `rule_id`, enfants et spans source; une racine seule
   ne suffit pas.
4. Fait pour cette extension v2 : positifs indépendants, négatifs autonomes,
   guillemets ouverts/fermés, `!` et `?`, conservation des abréviations,
   quote-transfer et round-trip. Toute extension ultérieure doit refaire
   ces contrôles.
5. Pour tout changement de grammaire, appliquer
   [GRAMMAR_CASE_FIX_PROTOCOL.md](GRAMMAR_CASE_FIX_PROTOCOL.md) :
   exemples indépendants, témoins négatifs, sensibilité du cas 359,
   qualité 120/120, contrastes 24/24 et comparaison exacte des 500
   unités avec budgets 50 000 / 500 000 inchangés.

**Aucun succès supplémentaire n'est revendiqué.** Tant que l'arbre
correct n'est pas démontré, le cas 64 reste dans la file des 26 résidus.
