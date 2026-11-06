# Cas 370 — incises adjectivales, participe passif et absolues coordonnées

> She was there, lifeless and inanimate, thrown across the bed, her head
> hanging down and her pale and distorted features half covered by her hair.

Base : `main` à `6eade432159151935c451bb1bfa570f64dc525ce` ; cohorte figée
de 500 phrases, WordNet 3.0, `parse_corpus_case` avec guillemets équilibrés,
budgets inchangés (50 000 éléments de forêt, 500 000 unités de k-best,
10 secondes par phrase dans le diagnostic global).

## Diagnostic

Avant modification, le cas 370 était `roots_without_valid_analysis` : la
forêt contenait 1 108 éléments, mais l'analyse complète de la phrase
n'était pas matérialisée. Les quatre descriptions finales n'ont pas la même
fonction grammaticale :

1. **lifeless and inanimate** est une incise adjectivale qui qualifie *She* ;
2. **thrown across the bed** est un participe passé passif suivi de son
   complément locatif *across the bed*, qui qualifie aussi *She* ;
3. **her head hanging down** est une construction absolue avec sujet propre,
   verbe en *-ing* intransitif et particule directionnelle ;
4. **her pale and distorted features half covered by her hair** est une
   construction absolue passive avec sujet propre, adverbe de degré et
   complément en *by*. Elle est coordonnée à la troisième.

Les deux absolues portent sur les parties du corps de *She* ; ce ne sont
pas deux clauses finies indépendantes. Les trois virgules sont des
délimiteurs réels, sans substitution du point final.

## Correction compositionnelle

Huit règles grammaticales spécifiques composent les constituants :

- `np_supplement_absolute_pronoun` : sujet pronominal de la clause matrice ;
- `np_absolute_possessive_head` et
  `np_absolute_possessive_adjectives_head` : sujets nominaux possessifs
  des deux absolues, avec ou sans adjectifs coordonnés ;
- `absolute_ing_particle` : sujet absolu + participe présent intransitif
  + particule ;
- `absolute_passive_adv_by` : sujet absolu + adverbe + participe passé
  transitif + complément en *by* ;
- `absolute_coordinated_ing_passive` : coordination de ces deux absolues ;
- `supplementary_passive_participle_pp` : participe passé avec PP locative ;
- `clause_locative_postposed_adjp_passive_and_absolutes` : clause matrice
  avec copule finie accordée, adverbe locatif, incises délimitées et deux
  absolues coordonnées.

Des vues lexicales contextuelles `PRONOUN-SUPPLEMENT-ABS`,
`POSS-SUPPLEMENT-ABS` et `V-SUPPLEMENT-ED` ne sont projetées que si le
lattice contient les indices indépendants des virgules, participes,
marqueur *by* et copule locative. **Les lectures WordNet originales, sens,
traits, identifiants, sources et spans sont conservés** ; leurs copies
typées ne sont pas une analyse lexicale alternative inventée.

Une première règle nominale trop ouverte rendait le témoin de dialogue
**359** saturé avant reconnaissance. Cette tentative a été rejetée : les
vues typées limitées au contexte empêchent l'explosion combinatoire sans
augmenter les budgets.

La flexion irrégulière de *throw* est aussi précisée : **threw** est
fini, **thrown** est un participe passé. Sans cette distinction, WordNet
exposait fautivement une lecture `V[ed]` de *threw*, acceptée comme passif.
L'entrée ne remplace aucun sens WordNet et les usages actifs/passifs sont
contrôlés en test.

## Arbre sélectionné — attaches vérifiées

```text
CLAUSE clause_locative_postposed_adjp_passive_and_absolutes
├── NP-SUPPLEMENT-ABS « She »
├── COPULA « was »
├── ADV « there »
├── COMMA « , »
├── ADJP « lifeless and inanimate »
├── COMMA « , »
├── PART-PASSIVE-PP « thrown across the bed »
│   ├── V-SUPPLEMENT-ED « thrown »
│   └── PP « across the bed »
├── COMMA « , »
└── ABS-COORD absolute_coordinated_ing_passive
    ├── ABS-ING « her head hanging down »
    │   ├── NP-ABS-POSS « her head »
    │   ├── V-INTRANSITIVE-ING « hanging »
    │   └── PARTICLE « down »
    ├── COORD « and »
    └── ABS-PASSIVE « her pale and distorted features half covered by her hair »
        ├── NP-ABS-POSS « her pale and distorted features »
        ├── ADV « half »
        ├── V[ed] « covered »
        └── PP-BY « by her hair »
```

Le rang 1 respecte les relations parent/enfant, les `rule_id`, les traits
verbaux et les spans exacts ; il s'arrête avant le point terminal. Les tests
ne se contentent pas de `completed=True`.

## Vérifications

Quatre tests dédiés dans `LocativeClauseWithCoordinatedAbsolutesTests` :

- cible épinglée 370 par `parse_corpus_case`, rang 1, attaches et provenance ;
- deux exemples indépendants avec verbes, adjectifs et lieux différents ;
- six contrastes de morphologie, ponctuation et valence rejetés ;
- distinction *threw/thrown* et maintien des deux usages de *throw*.

Le témoin officiel 359 et les exemples positifs indépendants passent.
Le smoke test (canonique, trie lazy, dialogues) passe. Le contrôle direct
conserve **120/120** annotations choisies, **24/24** contrastes positifs,
avec **9** acceptations négatives déjà connues, sans changement de seuil.

La suite intégrale `unittest discover` passe : **475 tests**, aucun échec.

La comparaison complète de la cohorte SHA-256
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`
donne **469/500 → 470/500**. Un seul index change : **370** passe de
`roots_without_valid_analysis` à `complete`. Les 499 autres statuts sont
**strictement identiques**, ainsi que les empreintes de phrase et le mode
`quote_balanced` par index : aucune ancienne réussite perdue, aucun nouvel
échec ou dépassement de budget. Restent les quatre dépassements de forêt,
le délai de l'index 312 et les 30 cas non complets restants.

Ce bilan atteste la non-régression opérationnelle, et les tests dédiés
attestent les attaches de la phrase 370 ; il ne certifie pas chaque arbre
des 500 phrases comme linguistiquement parfait.
