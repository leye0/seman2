# Contrat public des diagnostics grammaticaux — Layer 1, P0

Ce contrat s'applique à **`Parser.parse`**, seule porte d'entrée syntaxique.
Il ne change ni les grammaires stricte et marquée, ni les budgets, ni le
classement des arbres, ni les caractères du texte ou la préparation des
guillemets. P0 **n'est pas un détecteur universel de fautes** : il formalise
les preuves créées par les règles marquées déjà modélisées (cas 463 et 480).

## Statuts indépendants

Les propriétés de `ParseResult.as_dict()` et `ParseReport.as_dict()` sont :

| Champ | Sémantique |
| --- | --- |
| `completed` | Booléen historique inchangé : analyse complète certifiée disponible. |
| `parse_status` | `complete` / `incomplete`, sans jugement sur la langue. |
| `grammatical_status` | **Sur l'arbre de rang 1 seulement** : `standard` (aucune règle marquée dans cet arbre), `nonstandard_attested` (au moins un conflit explicitement licencié), ou `inconclusive` (pas d'arbre complet). |
| `diagnostic_scope` | `selected_complete_tree` ou `none`. |
| `search_limitations` | Causes observables : `recognition_budget_exceeded`, `kbest_budget_exceeded`, `dialogue_recognition_budget_exceeded`, `dialogue_kbest_budget_exceeded`, `no_certified_complete_analysis`. |
| `ambiguity` | Nombre d'arbres complets **matérialisés** : `examined_complete_trees`, `marked_trees`, `unmarked_trees`, `exhaustive=false`. |

`standard` veut dire « sans écart *marqué* dans la dérivation retenue
par la grammaire actuelle », **pas** « grammaticalement certifié dans tous
les contextes ». Une alternative non marquée peut être valide ou mal
rattachée; son existence interdit toute affirmation certaine sur une faute
*de la phrase entière*. Les `k-best` ne sont pas exhaustifs. Les plafonds
et absences de parses restent inconclusifs : **jamais de faute déduite de
`completed=False`**. Le statut de l'arbre et ses limites sont rapportés
séparément.

## Preuve locale

`ParseResult.usage_deviations()` renvoie les conflits du seul arbre complet
retenu. Chaque `UsageDeviation` conserve les champs historiques :
`kind`, `relation`, `rule_id`, `parent_span`,
`subject`/`predicate` (surfaces, `analysis_span`, `features`),
`constraint`, `expected`, `observed`, `register`, `intent`.

La sérialisation ajoute :

- `evidence.type=explicit_marked_grammar_rule` et le `rule_id` :
  **seule** une règle de grammaire avec une déclaration de provenance
  `usage_deviation` peut produire cette preuve.
- `evidence.parent/subject/predicate` : catégorie et `path` (indices
  d'enfants depuis la racine **du meilleur arbre**), plus les `rule_id`
  des constituants lorsqu'ils existent. Les paths distinguent les deux
  occurrences de `says they` / `they says` dans le cas 480.
- Pour chaque côté, son `reference_span` et `reference_mapping`;
  pour le parent `parent_reference_span` et `parent_reference_mapping`.
  Valeurs du mapping : `exact`, `unavailable`, `not_provided`.
  Un mapping absent ou impossible n'est **jamais deviné** ni présenté
  comme le span du texte source.
- `intent_provenance` : `null` avec `intent=unknown`, par défaut. Une
  intention non inconnue exige une provenance explicite d'annotation;
  la syntaxe seule ne la déduit pas.

La preuve vérifie deux enfants **distincts**, réellement inclus dans le
parent et ayant les traits précis `expected != observed`. Elle échoue
fermement sur une déclaration contradictoire ou mal localisée. Des
occurrences distinctes sont conservées; des certifications strictement
identiques sont dédupliquées. Aucune forme lexicale n'est modifiée.

Les offsets d'analyse sont demi-ouverts, dans `ParseResult.text`.
Un `Parser.parse` ordinaire ne connaît pas l'origine d'un corpus.
Sur Gutenberg, **toujours** utiliser le préparateur canonique et passer
son mapping explicite lors de la sérialisation :

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case

prepared, lattice, result = parse_corpus_case(
    parser, case, allow_marked_deviations=True,
)
diagnostic = result.as_dict(reference_span=prepared.reference_span)
```

`reference_span` désigne exactement les offsets de `case["text"]`, la
référence figée du cas, **pas** des offsets globaux dans le roman ni dans
`case["source_text"]`. Les guillemets synthétiques restent sans
correspondance. Sans `reference_span`, les offsets d'analyse sont
toujours exposés, mais aucune origine n'est affirmée.

## Validation et limites restantes

- `test_usage_diagnostic_contract.py` vérifie deux écarts dans un arbre,
  chemins vers les nœuds, coordonnées, mappings exacts ou refusés,
  déduplication, preuve contradictoire rejetée, intention sans source
  rejetée, non-complétion et plafonds inconclusifs, alternatives connues.
- `test_case_480_marked_dialogue.py` vérifie l'arbre réellement choisi,
  les deux écarts avec leurs offsets du cas Gutenberg, et les incises,
  thème, vocatif, présentative et ellipse correctement attachés.
- Les témoins 463, les phrases régulières et contre-exemples, le cas
  saturé 359, le smoke, la qualité 120/120 et la cohorte 500 restent
  soumis aux validations du protocole.

P1–P3 restent à faire : nouvelles familles de contraintes, preuves
prudentes sans analyse globale, diagnostics et incertitudes plus riches,
corpus annoté de fautes, métriques indépendantes de précision. **Absence
d'un `UsageDeviation` ne signifie pas absence d'anomalie.**

## P1, première tranche — accord du prédicat fini dans une citation

Quatre règles supplémentaires sont disponibles **seulement** lorsque
`allow_marked_deviations=True` rencontre une citation explicitement balisée :
`CLAUSE → NP VP` avec (a) sujet 3pl / prédicat 3sg,
(b) sujet 3sg / prédicat 3pl, (c) sujet 1sg / prédicat 3sg,
ou (d) sujet 3sg / prédicat 1sg. Seuls les NP avec le trait **pronominal** positivement établi
sont admis dans cette première tranche. Les NP/VP conservent leurs
traits réels; le prédicat est fini et actif et le trait conflictuel
est positivement établi des deux côtés. Ce sont des **alternatives
marquées**, jamais de la grammaire strictement permissive.

`usage_deviations[].predicate` désigne le VP entier, avec son span
exact. Lorsqu'**un seul** candidat lexical fini à l'intérieur du
VP porte **dans ses traits lexicaux d'origine** le trait observé, la sortie ajoute
`evidence.predicate_head` : surface, traits, catégorie, chemin
complet dans l'arbre, offsets d'analyse et mapping source
(optionnel). Si aucune tête unique n'est prouvée, ce champ est
absent : aucun span verbal n'est inventé.

`register=unknown` et `intent=unknown` pour ces nouvelles règles.
Une dérivation marquée sur le meilleur arbre n'établit ni un dialecte
ni l'intention, et ne certifie pas la faute de toutes les lectures.
Le mode strict, la préparation des citations et les budgets
restent identiques. Morphologie, valence, ordre et diagnostic local
sans arbre restent à développer dans P1/P2.
