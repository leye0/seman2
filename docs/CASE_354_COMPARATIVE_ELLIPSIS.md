# Cas 354 — copule elliptique et comparaison avec relative finale

> This valley is more wonderful and sublime, but not so beautiful and
> picturesque as that of Servox, through which I had just passed.

Base : `main` à `5dd31b3f87e837f19cde2aa8b24ebc1efb0473ab` ;
cohorte figée de 500 phrases, WordNet 3.0, `parse_corpus_case` par défaut
(texte équilibré), budgets inchangés (50 000 éléments de forêt,
500 000 unités de k-best et 10 secondes par phrase dans le diagnostic global).

## Cause et exigences syntaxiques

La phrase originale possède les analyses de ses constituants isolés, mais
aucune analyse complète matérialisée (`roots_without_valid_analysis`).
La première proposition *This valley is more wonderful and sublime* était
déjà reconnue. Deux manques empêchaient leur combinaison :

1. Après la virgule et *but not*, la copule **is** n'est pas répétée : le
   second groupe adjectival est un prédicat contrasté du **même sujet**.
2. Dans *so beautiful and picturesque as that of Servox*, le standard
   **as that of Servox** porte sur **les deux adjectifs**. La relative
   finale *through which I had just passed* décrit le groupe entier
   *that of Servox* (la vallée), pas seulement le nom propre *Servox*.

Une première tentative obtenait `completed=True` mais rattachait la relative
à *Servox* à travers `np_relative_pp_comma_pair`, en traitant même le point
final comme la virgule fermante de cette construction. **Cette analyse a
été rejetée** : la reconnaissance ne suffit pas à valider une phrase.

## Correction généralisable

- `vp_copular_contrast_negated_ellipsis` : une **copule finie réellement
  attestée** régit deux groupes adjectivaux contrastés, séparés par une
  virgule littérale, un coordinateur et une négation explicite. Aucune
  règle générale `NEG + ADJP -> VP finite` n'est introduite.
- `adjp_so_coord_adjectives_as_np` : *so* équatif suivi de deux adjectifs
  coordonnés puis de *as + NP*, avec un seul standard comparatif commun.
  Un sens lexical `DEGREE[equative_so=true]` de *so* est ajouté **sans
  supprimer** les lectures existantes du mot.
- `np_relative_pp_equative_final_standard` et
  `adjp_so_coord_adjectives_as_relative_standard` : le standard comparatif
  partitif (*that of Servox*) reçoit sa relative en **fin d'énoncé**,
  sans consommation du point final comme fausse virgule et sans rattachement
  interne au nom propre.
- La vue `DET-EQUATIVE-PARTITIVE` ne démarre cette dernière construction
  que si le lattice contient les indices lexicaux du *so … as*, du partitif
  *of* et de la relative prépositionnelle. Les hypothèses `DET` d'origine,
  leurs traits, sources et sens restent toutes disponibles. Sans cette
  limitation, le témoin 359 tombait en saturation sur le chemin dialogue.

## Arbre sélectionné : rattachements contrôlés

```text
CLAUSE clause_np_vp
├── NP « This valley »
└── VP vp_copular_contrast_negated_ellipsis
    ├── COPULA « is »
    ├── ADJP « more wonderful and sublime »
    ├── COMMA « , »
    ├── COORD « but »
    ├── NEG « not »
    └── ADJP adjp_so_coord_adjectives_as_relative_standard
        ├── DEGREE « so »
        ├── ADJ « beautiful »
        ├── COORD « and »
        ├── ADJ « picturesque »
        ├── CONJ « as »
        └── NP-EQUATIVE-REL-TAIL
            np_relative_pp_equative_final_standard
            ├── DET-EQUATIVE-PARTITIVE « that »
            ├── PREP « of »
            ├── NP « Servox »
            ├── COMMA « , »
            └── REL-CLAUSE-PP rel_pp_finite_np_vp
                ├── REL-PP « through which »
                ├── NP « I »
                └── VP « had just passed »
```

L'arbre de rang 1 s'arrête **avant** le point terminal. Les assertions
du test épinglé vérifient les catégories enfants, les `rule_id`, les spans,
la portée de la comparaison, l'antécédent de la relative et la conservation
des lectures lexicales originales.

## Vérification

Tests ajoutés dans `CopularContrastAndEquativeRelativeTests` :

- arbre sélectionné du cas 354 et ses attaches exactes;
- variantes positives indépendantes de copule elliptique et de comparaison
  coordonnée (*The lake was calm, but not deep*;
  *This lake is not so calm and clear as the river*);
- refus structurel des variantes sans virgule requise, sans négation,
  avec *than* à la place de *as*, et sans pronom relatif oblique licencié;
- conservation des candidats originaux `so` et `DET` malgré les vues typées;
- témoin 359 de dialogue, dont la saturation a été détectée et réparée
  **avant** validation globale.

Le contrôle direct `validate_direct_grammar` reste à **120/120** faits
syntaxiques annotés, **24/24** contrastes positifs et **9** acceptations
négatives déjà connues. `scripts.smoke_layer1` passe pour le canonique,
le trie lazy et les dialogues.

La suite complète `unittest discover` passe : **467 tests**, aucun échec,
dont les nouvelles assertions de rattachement et l'ancien témoin 359.

La comparaison complète, **à paramètres identiques** et sur la cohorte
SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`,
donne **468/500 → 469/500**. Un seul index change : **354** passe de
`roots_without_valid_analysis` à `complete`. Aucun ancien succès perdu ;
les quatre dépassements de budget forêt et le délai du cas 312 restent
inchangés. Même nombre de cas contenant une saturation de forêt (21),
dont 17 demeurent néanmoins reconnus : ils ne sont pas considérés comme
des preuves de justesse grammaticale.

Ces ensembles ne certifient pas la justesse intégrale de chaque arbre de
la cohorte ; la phrase 354 possède des assertions structurelles explicites.
