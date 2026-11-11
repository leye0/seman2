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

- `superparser/data/function_words.jsonl` : seule lecture
  additionnelle de `wherever` en
  `WH-NOM[wh, wh_adverbial, free_relative]`. Les lectures WordNet
  ADV et **toutes les lectures historiques de `to`** restent intactes.
- `superparser/data/grammar.jsonl` : une règle productive,
  `np_dash_locative_free_relative`, compose
  `DASH[dash_kind=em] + WH-NOM[wh,wh_adverbial,free_relative] + CLAUSE`
  → `NP[locative,free_relative]`. La règle préexistante
  `pp_prep_np: PREP + NP → PP` construit alors
  `to + NP("--wherever it is")`. **Aucune règle nouvelle ne commence
  par `PREP`**, et les 500 cas n'héritent pas d'un état de recherche
  supplémentaire à chaque préposition.

La construction spéciale exige à la fois un tiret explicite et un
WH-NOM locatif de relative libre. Elle ne reconnaît pas
`to--whatever it is` via cette nouvelle règle. La préposition
est résolue par la composition PP historique : cette étape est
syntaxique et n'interdit pas catégoriquement des prépositions autres
que `to`. La sélection sémantique des destinations relève d'une
vérification ultérieure; ne pas prétendre rejeter absolument
`with--wherever she is`.

## Arbre de rang 1 : attestations et spans

L'[audit ciblé de la variante ancrée sur le tiret](https://github.com/leye0/seman2/actions/runs/42957007535)
confirme l'arbre de rang 1 et ses spans, avec **4 tests de structure**. Le témoin 359 redevient complet avec **1 472 nœuds**, **48 529 états partiels**, identiques à la référence. Son drapeau `forest_budget_exceeded` est **déjà vrai dans la référence** : la vérification pertinente est la racine complète et le même profil de recherche.

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
- Son complément de destination conserve la composition existante
  `PP pp_prep_np` sur **[85,103]** :
  `PREP "to"` puis `NP np_dash_locative_free_relative`
  sur **[87,103]**. Cette dernière possède exactement trois enfants :
  `DASH "--"`, `WH-NOM "wherever"`,
  `CLAUSE "it is"` (copule finie). La destination reste attachée
  au prédicat `take you`, jamais au nom précédent.
- Le test vérifie la structure et les positions **sur le meilleur
  arbre réellement sélectionné** ; il ne se contente pas de vérifier
  l'existence d'une analyse concurrente.

## Tests ciblés et limites

- Cible : citation originale extraite via `extract`, puis
  **`parse_corpus_case`**, source/spans exacts et rang 1.
- Positif indépendant : `I will take her to--wherever she is.`
- Contrôle sans tiret : `I shall take you to wherever it is.`
- Négatif de composition spécialisée :
  `I will go to--whatever it is.` (aucun nouveau nœud nominal locatif).
- Tests de bornage : 31 tests existants de segmentation/provenance,
  4 nouveaux tests structurels, script de sondes complet.

La nouvelle lecture et la nouvelle règle sont généralisables à la
construction locative avec interruption, mais ne garantissent pas
la correction de toutes les relatives du corpus. Le témoin sensible
**359** est maintenant restauré au nombre exact de nœuds et d'états.
La qualité **120/120**, les contrastes **24/24**, les négatifs acceptés
et la comparaison stricte des **500 statuts** restent les portes
de validation de l'intégration.
