# Cas 491 — concession, passif participial et relative locative

**Statut : non corrigé.** Plusieurs sous-constituants ont une analyse
structurale, mais leurs meilleurs arbres ne respectent pas la morphosyntaxe.
Leur complétion locale ne doit pas être comptée comme un succès du cas entier.

## Provenance

- Base de travail `main` : `3006e02a75827e1f241df7c5dc6c6785eb877123`.
- Dernier bilan **canonique des 500** : commit de code
  `5b757eb329ab706ef082a939f070d3dad9ee97af`,
  [CI 42527736728](https://github.com/leye0/seman2/actions/runs/42527736728),
  **474/500** ; cohorte figée
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- CI ciblée : commit diagnostic `ecf5e3ed7d96b879bbeece3e234ce72c884aafe9`,
  [exécution 42552398902](https://github.com/leye0/seman2/actions/runs/42552398902)
  **réussie**. Artefact `residual-grammar-validation`, fichiers
  `case491-full-audit.log` et `case491-constituents.log`.
- Conditions inchangées : WordNet 3.0, `QUOTE_BALANCED`, `max_items=50000`,
  `kbest_work_limit=500000`. Le cas Gutenberg entier est toujours préparé
  par `parse_corpus_case`, jamais reparsé depuis le texte brut avec une
  normalisation ad hoc.
- Index 491, livre 120 (Treasure Island), `120:1a3c9fc15b2f59db` :

  > But he was dead enough, for all that, being both shot and drowned, and was food for fish in the very place where he had designed my slaughter.

## Diagnostic canonique

Le résultat est `roots_without_valid_analysis`, **aucun arbre choisi** :

| Mesure | Résultat |
| --- | ---: |
| Jetons / candidats lexicaux | 32 / 164 |
| Nœuds structuraux de racine | 1 |
| Nœuds de forêt | 1 185 |
| États partiels | 47 825 |
| Propositions de partiels | 57 689 |
| Travail k-best | 20 187 unités |
| Budget forêt dépassé | non |
| Budget k-best dépassé | non |

Une racine symbolique **n'est pas un arbre grammatical validé**. Aucune
catégorie lexicale entièrement absente n'est constatée. Le bilan canonique
reste à 474/500 : aucun code de grammaire n'a été modifié dans cette livraison.

## Isolation des sous-constituants

Les probes de phrases **construites localement** utilisent l'API
`Parser.parse` avec les mêmes limites. Ils ne remplacent pas la cohorte.

| Sous-phrase / catégorie | Statut | Meilleur arbre ou problème |
| --- | --- | --- |
| `But he was dead enough` | complète | `coord_clause` > `clause_np_vp` > `vp_cop_adj_adv` ; acceptable |
| `for all that` (PP) | complète | `pp_prep_np`, analyse littérale, pas la valeur concessive de l'incise |
| `He was dead enough, for all that` | complète | `clause_final_comma_benefactive_pp` : **attache bénéficiaire erronée** |
| `being both shot and drowned` (VP) | complète | `vp_coord_finite` : **analyse finie fausse**, détails ci-dessous |
| `shot and drowned` (`PASSIVE-PART`) | incomplet | Séquence passive coordonnée non démontrée |
| `He was dead enough, being both shot and drowned` | complète | `vp_comma_coord` avec le même faux VP fini |
| `He was dead enough, for all that, being both shot and drowned` | complète | `clause_comma_coord`, `for` pris pour une coordination causale ; faux rattachement |
| `He was dead enough and was food for fish` | complète | `clause_np_vp` avec `vp_coord_finite` ; coordination du sujet partagé justifiée |
| `He was food for fish in the very place where he had designed my slaughter` | incomplète | Sous-blocage du groupe nominal avec relative locative, cause fine encore à établir |
| Phrase complète **sans** `But` initial | incomplète | Ce coordonnant initial n'est pas l'unique obstacle |

La mauvaise analyse de la parenthèse participiale est particulièrement nette :

```text
VP vp_coord_finite [0:27] being both shot and drowned
  VP vp_cop_np [0:15] being both shot
    COPULA being
    NP np_det_adj both shot
  COORD and
  VP vp_intransitive drowned
```

Ici `being` est non fini et gouverne une **coordination de participes passifs**,
et non un prédicat copulaire fini plus un verbe fini intransitif. Le candidat
lexical `AUX-BE[vform=ing]` existe, ainsi que les lectures
`shot[V,vform=ed]` et `drowned[V,vform=ed]`. Il manque donc au minimum une
composition sélectionnée correctement, pas simplement une étiquette de mot.

Pour la relative `where he had designed my slaughter`, les lectures lexicales
de `where` sont `WH-NOM` et `WH-NOM[wh_adverbial=true]`. La grammaire possède
des relatives obliques explicites, mais les éléments examinés ne démontrent
pas encore une règle *restrictive locative* adéquate pour `place where ...`.
Une règle générique qui raccorderait n'importe quel `where CLAUSE` à n'importe
quel nom serait trop permissive : il faudra une sélection locative prouvée
et des contrastes négatifs.

## Pourquoi ne pas ajouter immédiatement trois règles

La phrase a **au moins trois problèmes distincts** de portée : concession
(`for all that`), participiale passive incidente (`being both ... and ...`),
et relative locative (`place where ...`). Les analyses locales « complètes »
produisent actuellement des rattachements fautifs. Un patch seulement destiné
à obtenir `completed=True` pourrait cacher ces défauts, ouvrir énormément
de partiels dans la forêt et faire régresser le cas sensible **359**.

Le prochain correctif doit prouver dans cet ordre :

1. Une construction concessive réellement distincte de `for` bénéficiaire,
   avec exemples indépendants et contextes où la concession n'est pas licite.
2. `being` **non fini**, avec `both` portant sur deux participes `ed`, un
   supplément lié au bon sujet et aucune lecture finie de substitution.
3. Une relative locative attachée au bon antécédent, sans autoriser les
   relatives `where` sur les noms non locatifs.
4. L'arbre **sélectionné** complet : sujets, prédicats coordonnés, incises,
   relative, spans et attaches inspectés, puis vérifications 359, qualité
   120/120, contrastes 24/24, tests négatifs et comparaison 500 cas à budgets
   constants.

**Verdict :** diagnostic et CI ciblée réussis ; pas de correction grammaticale
certifiée, score inchangé, cas 491 conservé parmi les non résolus. Le curseur
de la file est avancé à **491**, et le prochain cas déterministe est **497**.
