# Cas 497 — complément nominal rectifié, incise et portée de deux PP

**Statut : non corrigé.** Deux règles expérimentales ont produit un arbre
complet mais syntaxiquement inexact et ont fait régresser le témoin 359. Les
deux essais sont conservés uniquement dans l'historique Git ; aucune de ces
règles n'est conservée dans la grammaire active.

## Provenance et cible

- Base de départ `main` : `f9ec667b06b741c52e870a9b088abe457ff918b4`.
- Diagnostic isolé sans changement grammatical : `24b3c40a5e38bed9c2fcd20f118c2b24f3055521`,
  [CI 42553190840](https://github.com/leye0/seman2/actions/runs/42553190840), verte.
- Essai direct : `e2a4fd94ffc6afbe8c2989a69c76170950b2ac02`,
  [CI 42553670350](https://github.com/leye0/seman2/actions/runs/42553670350), échec.
- Essai en constituants typés : `98ca189fb29f11f9ee2a2155cba08e59241e33c4`,
  [CI 42554044343](https://github.com/leye0/seman2/actions/runs/42554044343), échec.
- Restauration du code grammatical initial et avancement documentaire de la
  file : `df234cf804fbc95c181b102629cd3013f2f1e8ab` ;
  [CI de grammaire ciblée 42554373845](https://github.com/leye0/seman2/actions/runs/42554373845)
  **verte** et [CI de dialogues 42554374055](https://github.com/leye0/seman2/actions/runs/42554374055)
  **verte**. Les fichiers `grammar.jsonl` et `syntax_lexicon.jsonl` sont
  bit à bit identiques à ceux du commit de diagnostic initial.
- Cohorte figée SHA-256
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
  Dernier bilan intégral valide : code `5b757eb329ab706ef082a939f070d3dad9ee97af`,
  **474/500** ; aucun nouveau bilan intégral n'est revendiqué.
- Livre 120 (*Treasure Island*), index 497,
  identifiant `120:1d6c54a55efa9bbd` :

> But there was no sign of reawakening courage in his followers, rather, indeed, of growing terror at the irreverence of his words.

Le parse original a été invoqué par `parse_corpus_case` et la même forme
`QUOTE_BALANCED` : 26 jetons, 89 candidats lexicaux, une racine structurale,
774 nœuds de forêt, 22 008 états partiels, 3 234 unités de travail k-best,
aucune saturation, mais **`roots_without_valid_analysis`**.
Limites : 50 000 items, 500 000 unités k-best, WordNet 3.0.

## Rattachements requis, vérifiés séparément

Les deux membres du contraste sont **deux réalisations concurrentes du
complément en `of` de `sign`** :

1. « of reawakening courage in his followers » : « in his followers »
   relève du courage qui se réveille, pas d'un emplacement de la proposition
   existentielle.
2. « rather, indeed, of growing terror at the irreverence of his words » :
   l'opérateur de rectification est « rather », avec « indeed » comme incise.
   « at the irreverence of his words » modifie la terreur croissante,
   **pas** « there was » ; « of his words » dépend d'« irreverence ».

Les sous-constituants sans rectification se reconnaissent :

| Fragment / but | Résultat de base | Défaut pertinent |
| --- | --- | --- |
| « There was no sign of reawakening courage in his followers. » | complet | rang 1 `clause_there_pp` rattache `in his followers` à la proposition, même si le NP complet correct existe indépendamment |
| NP « no sign of reawakening courage in his followers » | complet | `np_det_n_of` > `np_pp_mod` ; bon rattachement de `in`, mais `reawakening courage` lu comme gérondif verbal transitif plutôt qu'un groupe adjectival possible |
| NP « growing terror » | complet | `np_bare` > `n_adj_n`, adjectif `growing` reconnu |
| PP « of growing terror at the irreverence of his words » | complet | rang 1 `np_of` : `of his words` devient dépendant de `growing terror at the irreverence` plutôt que d'`irreverence` |
| « There was no sign of reawakening courage, rather, indeed, of growing terror. » | incomplet | manque de composition pour l'opérateur rectificatif |

La complétion locale du NP ou du PP ne vaut donc pas preuve d'un arbre
correct pour la phrase entière.

## Essai 1 : règle nominale directe

La règle `np_det_n_of_corrective_with_incise` a lié les deux compléments en
un NP, avec un sens lexical supplémentaire `rather` de rectification.
La citation devenait `completed=True` (774 nœuds, 22 061 états) mais le
rang 1 était :

```text
CLAUSE coord_clause
  CLAUSE clause_there_pp
    NP np_det_n_of_corrective_with_incise
      ... of reawakening courage in his followers,
          rather, indeed, of growing terror
    PP pp_prep_np
      at the irreverence of his words
```

Le PP final est **hors de la correction**. Un test existant sur le témoin
359 (« The Turk allowed this intimacy ... ») perdait aussi sa complétion.
Ajouter un sens lexical global à « rather » a été trop coûteux dans la
forêt partagée.

## Essai 2 : queue rare et opérateur réutilisé

La seconde variante, `np_of_complement_corrective_with_incise`, a exigé un
NP initial marqué par `np_det_n_of`, puis une queue commençant par l'adverbe
rectificatif. Les deux variantes de queue, avec et sans PP final, visaient
à contenir la modification de « growing terror ». Le sens existant de
« rather » a été réutilisé, sans ajouter de candidat lexical.

Résultats sur le cas 497 : 846 nœuds, **24 787 états partiels**, 3 998
unités k-best, et `completed=True`. Cependant le rang 1 était encore :

```text
CLAUSE coord_clause
  CLAUSE clause_there_pp
    NP np_of_complement_corrective_with_incise
      NP np_det_n_of
        no sign of reawakening courage in his followers
      OF-CORRECTION-TAIL of_correction_tail_incise
        rather, indeed, of growing terror
    PP pp_prep_np
      at the irreverence of his words
```

Le test positif indépendant (« There was no trace of progress, rather,
indeed, of decline. ») et le négatif (« rather, suddenly, of decline »)
passaient, **mais le test de l'arbre cible échouait**, et le cas 359 ne
produisait plus de racine (`structural_root_nodes=0`). La forêt de 359,
proche de son plafond habituel, n'a pas le droit de perdre son arbre pour
faire reconnaître 497. L'essai était donc une **régression**, non un gain.

## Piste de reprise, sans solution présumée

Étudier la préférence d'attachement du PP à l'intérieur de la correction
nominale et du complément « terror », tout en gardant les nouvelles
constructions rares invisibles aux phrases sans opérateur rectificatif.
Vérifier la distinction *participial adjective* / *gerund* de
« reawakening courage ». Conserver un test sur la totalité de l'arbre
sélectionné et le témoin 359 : ne jamais compter 497 comme gagné sur la
simple valeur `completed=True`.

La file avance à `last_attempted_index=497` mais conserve 497 comme
`roots_without_valid_analysis`. La prochaine position est **8**.
