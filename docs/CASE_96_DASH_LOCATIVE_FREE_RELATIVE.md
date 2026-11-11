# Cas 96 — destination locative après tiret dans un dialogue

**Statut : correction candidate de la grammaire, validation globale en attente.**
Le cas est une construction compositionnelle, non une substitution de texte.
Le succès n'est revendiqué pour le corpus gelé qu'après comparaison complète
de la CI des 500 cas.

## Référence immuable

- Livre : Dickens, *David Copperfield*, Gutenberg 766 ; index **96**,
  ordinal **1512**, `case_id=766:a6bdc4b39fc21c48`.
- Cohorte originale `QUOTE_BALANCED` SHA-256 :
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- Base : `main` `6d536267140da93f80c36111e8953a5089e4ee89`,
  strict **474/500** avant la modification.
- WordNet de référence **3.0**, forêt **50 000**, k-best **500 000**,
  délai canonique **10 secondes**. Aucun plafond augmenté.

Texte original, guillemets et graphie dialectale strictement conservés :

> ‘And there I shall take you to the stage-cutch, and the stage-cutch that’ll take you to--wherever it is.’

Avant : `roots_without_valid_analysis`, **505 nœuds**, **21 773 états
partiels**, 84 candidats lexicaux, aucun mot sans candidat, aucun
dépassement de budget. Le sous-parseur de dialogue avait une racine
structurelle mais aucune analyse complète valide. Ce n'est pas un défaut
de segmentation, d'orthographe dialectale ou de guillemets transférés.

## Causes isolées par construction

L'[audit WordNet 3.0 42954486627](https://github.com/leye0/seman2/actions/runs/42954486627)
a établi que les éléments suivants étaient déjà reconnus et correctement
composables : `I shall take you to the stage-cutch`, la relative modale
`the coach that'll take you to the town`, et la coordination nominale
`the coach, and the train` via `np_list_last`.

Deux lacunes étaient nécessaires à expliquer le rejet :

1. `wherever` n'avait qu'une lecture **ADV** dans le réseau lexical,
   tandis que `where` avait déjà `WH-NOM[wh=true]`. La relative locative
   nominalisée `wherever it is` ne pouvait donc servir de destination
   à `to`.
2. Le tiret littéral `--`, déjà reconnu comme `DASH[dash_kind=em]`,
   interrompait le lien entre `to` et la proposition locative. Aucune
   composition prépositionnelle typée n'acceptait cette pause explicite.

## Implémentation candidate

- `superparser/data/function_words.jsonl` : lecture additionnelle de
  `wherever` en `WH-NOM[wh, wh_adverbial, free_relative]`,
  **sans retirer** les lectures WordNet ADV. L'entrée `to` en
  `PREP` reçoit `locative_destination=true`, un trait indépendant qui
  ne supprime pas la lecture `TO`.
- `superparser/data/grammar.jsonl` :
  - `wh_clause_free_locative_ever` :
    `WH-NOM[wh,wh_adverbial,free_relative] + CLAUSE` →
    `WH-CLAUSE[locative,free_relative]`.
  - `pp_dash_interrupted_locative_relative` :
    `PREP[locative_destination] + DASH[dash_kind=em] +
    WH-CLAUSE[locative,free_relative]` →
    `PP[locative]`.

Les contraintes évitent d'accepter, par **cette règle**, un groupe
`with--wherever she is` ou une relative non locative
`to--whatever it is`. Les autres lectures historiques continuent
d'exister; un ancien parse tolérant peut encore analyser de tels
exemples par des règles indépendantes et ne doit pas être présenté
comme un rejet absolu.

## Arbre de rang 1 : attestations et spans

L'[audit restreint 42955227024](https://github.com/leye0/seman2/actions/runs/42955227024)
réussit, avec **5 tests d'attachement** et les contrôles de provenance.

- `dialogue_unattributed` couvre **[0,105]**, citation entière avec les
  guillemets. `DIRECT-SPEECH dialogue_quote_clause_comma` conserve la
  ponctuation d'origine.
- `CLAUSE coord_clause` → `clause_front_adv_nocomma` →
  `clause_np_vp` : sujet **I** en **[11,12]**, prédicat modal
  `shall take you ...`.
- `PP pp_prep_np` couvre **[28,103]**, avec `to` et le groupe
  `NP np_list_last` **[31,103]** :
  `the stage-cutch` **[31,46]**, virgule et `and`, puis
  `NP np_relative_subj` **[52,103]**.
- Cette seconde occurrence de `stage-cutch` porte
  `WH-SUBJ wh_subj_clause` **[68,103]**, à prédicat modal `’ll take`.
- Son complément de destination `PP pp_dash_interrupted_locative_relative`
  couvre **[85,103]** et possède exactement trois enfants :
  `PREP "to"`, `DASH "--"`,
  `WH-CLAUSE "wherever it is"`.
  Le dernier contient `WH-NOM "wherever"` et
  `CLAUSE "it is"` sous `wh_clause_free_locative_ever`.
- Les trois premières alternatives de l'essai non restreint retenaient
  cette même structure critique ; l'essai restreint le confirme via
  l'arbre réellement sélectionné.

## Tests ciblés et limites

- Cible : citation originale extraite via `extract`, puis
  **`parse_corpus_case`**, source/spans exacts et rang 1.
- Positif indépendant : `I will take her to--wherever she is.`
- Contrôle sans tiret : `I shall take you to wherever it is.`
- Négatifs de composition spécialisée :
  `I will go with--wherever she is.` et
  `I will go to--whatever it is.`
- Tests de bornage : 31 tests existants de segmentation/provenance,
  5 nouveaux tests structurels, script de sondes complet.

La nouvelle lecture et la nouvelle règle sont généralisables à la
construction locative avec interruption, mais ne garantissent pas
la correction de toutes les relatives du corpus. Le témoin sensible
**359**, la qualité **120/120**, les contrastes **24/24**, les négatifs
acceptés et la comparaison stricte des **500 statuts** restent les
portes de validation de l'intégration.
