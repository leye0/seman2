# Cas 371 — relative possessive, comparatif et possession graduée

> But to a Genevan magistrate, whose mind was occupied by far other ideas
> than those of devotion and heroism, this elevation of mind had much the
> appearance of madness.

Base : `main` à `13ef4f97445b9eb44a3b3609f2a5e686065b72ca` ; cohorte
figée SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a` ;
WordNet 3.0, `parse_corpus_case` en `quote_balanced`, 50 000 items de forêt,
500 000 unités de k-best et 10 secondes par phrase.

## Diagnostic et arbre attendu

Initialement : `roots_without_valid_analysis` (1 379 nœuds de forêt,
49 412 opérations de reconnaissance dans le diagnostic épinglé). La
reconnaissance structurelle ne produisait **aucun arbre complet valide**.
La phrase demande quatre rattachements indépendants mais compatibles :

1. La relative **whose mind was occupied…** modifie précisément
   **a Genevan magistrate**, objet de *to*, dans le PP frontal ; ses deux
   virgules encadrent cette relative non restrictive.
2. **far other ideas than those of devotion and heroism** est un groupe
   nominal comparatif : *far* porte sur *other*, et *than* introduit
   l'étalon de comparaison.
3. **those of devotion and heroism** est un groupe partitif coordonnant
   les deux noms (*devotion* **et** *heroism*), et non une coordination
   de propositions ou de groupes verbaux.
4. **had much the appearance of madness** est un prédicat de possession
   avec adverbe de degré avant son objet nominal. *Much* ne modifie pas
   directement *madness*.

Arbre de rang 1 sélectionné, en abrégé :

```text
CLAUSE coord_clause
├── COORD « But »
└── CLAUSE clause_front_pp_nocomma
    ├── PP pp_prep_np_possessive_subject_relative_pair
    │   ├── PREP-WHOSE-REL « to »
    │   ├── NP « a Genevan magistrate »
    │   │   └── N n_adj_n « Genevan magistrate »
    │   ├── COMMA « , »
    │   ├── REL-CLAUSE-POSS rel_poss_subject_finite_vp
    │   │   ├── REL-WH-NP « whose mind »
    │   │   └── VP vp_passive_by_flat
    │   │       ├── AUX-BE « was »
    │   │       ├── V « occupied »
    │   │       ├── PREP-BY « by »
    │   │       └── NP np_degree_comparative_other_than
    │   │           ├── ADV-DEGREE-OTHER-THAN « far »
    │   │           ├── ADJ-OTHER-THAN « other »
    │   │           ├── N « ideas »
    │   │           ├── PREP « than »
    │   │           └── NP np_anaphoric_partitive_coordinated
    │   │               ├── DET-COORD-PARTITIVE « those »
    │   │               ├── PREP « of »
    │   │               ├── NP « devotion »
    │   │               ├── COORD « and »
    │   │               └── NP « heroism »
    │   └── COMMA « , »
    └── CLAUSE clause_np_vp
        ├── NP « this elevation of mind »
        └── VP vp_have_degree_adverb_nominal_object
            ├── HAVE-DEGREE-NP « had »
            ├── ADV « much »
            └── NP « the appearance of madness »
```

## Correction compositionnelle

Six règles ajoutées, chacune avec des rôles/contraintes explicites :

- `rel_poss_subject_finite_vp` relie le sujet possessif *whose + nom*
  à un VP fini accordé.
- `pp_prep_np_possessive_subject_relative_pair` assemble préposition,
  antécédent nominal, relative et **deux virgules littérales** dans le
  PP frontal : la relative ne flotte pas dans la clause matrice.
- `np_comparative_other_than` et `np_degree_comparative_other_than`
  composent *other N than NP* avec ou sans adverbe de degré.
- `np_anaphoric_partitive_coordinated` construit *those of N and N*.
- `vp_have_degree_adverb_nominal_object` construit *had much the NP*.

Des vues lexicales contextuelles 
`PREP-WHOSE-REL`, `ADJ-OTHER-THAN`,
`ADV-DEGREE-OTHER-THAN`, `DET-COORD-PARTITIVE` et `HAVE-DEGREE-NP`
limitent le démarrage des règles à des **indices indépendants et
visibles** : antécédent/relative avec virgules, *other N than*, *far*
adjacent à *other*, *those of* et *HAVE much DET*.
La lecture `ADJ` de *Genevan* (gentilé) et la lecture de degré possessif
de *much* complètent le lexique, sans masquer les lectures/sens WordNet.
Les vues du lattice conservent le span, la source, les traits et les
identifiants de sens du candidat original.

Le témoin historique **359** a orienté ce filtrage. Une première
formulation trop ouverte du comparatif à *other* ouvrait trop de dérivations
sur « far other plans », **sans** étalon *than*. La vue de degré n'existe
désormais que quand *other + nom + than* est présent. Le cas 359 garde son
arbre de dialogue de rang 1 et son état de reconnaissance d'origine,
sans relèvement de budget.

## Vérifications

La classe `FrontedPossessiveRelativeAndOtherComparisonTests` contrôle
le rang 1 de la phrase 371, les spans et rôles parent/enfant,
la préservation des sens originaux, deux phrases indépendantes
(avec et sans *far*), l'absence de vues comparatives sans *than*,
et des contrastes de ponctuation, de relatif, d'accord et de degré.
Un contraste d'accord sans coordination finale évite une ambiguïté
**préexistante** de `vp_coord` où *honor* peut être lu comme verbe fini.

Le test de file d'attente, historiquement codé en dur sur l'index 370,
utilise désormais le curseur et les indices non résolus ; il restera
correct après chaque mise à jour de file.

Le smoke test passe. Le contrôle grammatical direct reste à
**120/120** annotations sélectionnées, **24/24** contrastes positifs et
**9** acceptations négatives connues, sans changement de seuil.
La suite intégrale `unittest discover` passe : **479 tests**, aucun
échec ni erreur. Les ressources JSON de référence et VerbNet ont été
restaurées dans l'environnement de validation après réinitialisation,
sans être modifiées dans le dépôt.

Le diagnostic complet de 500 phrases donne **470/500 → 471/500** depuis
le bilan validé de `main`. Le rapport de référence plus ancien, avant
les cas 202, 354 et 370, donnait 467/500 ; la comparaison index par index
montre exactement quatre changements depuis cette référence : **202,
354, 370 et 371** deviennent `complete`. Les **496** autres statuts,
empreintes de texte et modes de préparation restent inchangés. Aucune
réussite perdue, aucun nouveau dépassement de budget de forêt ou de
k-best, aucun nouveau délai. Les quatre anciens dépassements de forêt
et le délai du cas 312 restent inchangés.

La 371 passe de 1 379 à 1 428 nœuds de forêt, de 49 412 à 49 863
opérations de reconnaissance, sous le seuil fixe de 50 000.
La 359 garde exactement **1 472 nœuds, 49 842 opérations** et la racine
`dialogue_unattributed`, comme avant la correction.

La correction prouve les rattachements du **rang 1 de la cible** ;
le score de cohorte seul ne prétend pas certifier les autres arbres.
