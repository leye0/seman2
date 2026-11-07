# Cas 463 — coordination négative, interrogative indirecte et relative extraposee

## Etat : bloque, non compte comme corrige

- Base `main` : `62c48d97e58c46065d9200fef403ebfc9f3b5224`.
- Cohorte gelee : SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- Livre : *Treasure Island* (Gutenberg 120), index **463**.
- Original : `You've neither sense nor memory, and I leave it to fancy where your mothers was that let you come to sea.`
- Analyse `QUOTE_BALANCED` : `"You've neither sense nor memory, and I leave it to fancy where your mothers was that let you come to sea."` (guillemets synthetiques, provenance et texte source inchanges).
- Budgets de diagnostic : `max_items=50000`, `kbest_work_limit=500000`; WordNet 3.0 existant.

## Diagnostic reproductible

```bash
PYTHONPATH=superparser WORDNET_DICT=.cache/wordnet3/wordnet \
  python -m scripts.audit_novel_tree_quality \
  --indices 463 --wordnet-dir .cache/wordnet3/wordnet \
  --alternatives 2 --lexical-audit
```

Le resultat direct de `parse_corpus_case(parser, case)` :

| Mesure | Etat initial |
| --- | --- |
| `completed` | `false` |
| `root_rule` | `null` |
| `forest_nodes` | 693 |
| `budget_exceeded` | `false` |
| `lexical_candidates` | 109 |
| Diagnostic global de la ligne | `roots_without_valid_analysis` |

Trois difficultes **independantes** doivent etre resolues sans raccourci :

1. **Auxiliaire contracte / possession niee.** La matrice de `You've` contient `You` (`PRONOUN`, provenance `contraction-base`) et `'ve` (`HAVE`, provenance `contraction-clitic`). La regle transitive standard exige `V`, alors que `HAVE` est actuellement reconnu comme auxiliaire de parfait ou dans certaines constructions possessives typées. `You have neither sense nor memory.` est reconnu avec `VP/vp_transitive` et `NP/np_gerund_coord` ; `You've neither sense nor memory.` ne l'est pas. Une solution devra couvrir les possessifs contractes avec objet nominal coordonne negatif sans transformer arbitrairement tout `HAVE` en verbe lexical.
2. **Accord non standard explicite.** `your mothers` est nominal **pluriel** ; `was` est une copule **singuliere**. `where your mother was` se construit, mais `where your mothers was` non. Unifier de force `plural` et `singular`, modifier la graphie gelee ou forger une lecture lexicale de `mothers` serait une contamination. Une future prise en charge doit representer *l'accord dialectal* explicitement et le limiter a un contexte ou registre atteste, avec controles negatifs en anglais standard.
3. **Portee et attachement de la relative.** Dans la sequence `where your mothers was that let you come to sea`, `that let you come to sea` a pour antecedent `your mothers` ; elle n'est pas l'attribut nominal de `was`. Sur le temoin singulier `I leave it to fancy where your mother was that let you come to sea.`, l'arbre de rang 1 est **incorrect** : `NP/np_inf_rel` rattache `to fancy ...` a `it`, et `VP/vp_cop_np` prend `that let ...` comme attribut de `was` via `NP/np_wh_clause`. Il faut une construction structurelle pour la relative postposee ou extraposee, avec l'interrogative indirecte et le complement infinitif correctement rattaches au predicat principal.

Les temoins `I leave it to fancy where your mother was.` et `where your mother was that let you come to sea` possedent eux aussi des analyses dont les attaches ne sont pas acceptables. La completion de ces variantes n'est donc pas un critere de succes.

## Criteres pour une reprise

- **Positifs independants** : une coordination `neither N nor N` avec `have` contracte et autre vocabulaire ; une relative de sujet extraposee sous interrogative indirecte avec sujet au singulier ; un temoin dialectal explicitement marque et independant de cette citation.
- **Negatifs** : `neither` sans `nor` ne doit pas autoriser la meme construction correlative ; le changement de nombre ne doit pas permettre `the mothers was` dans un contexte standard ; la relative ne doit pas pouvoir se rattacher a la copule comme attribut.
- **Cible obligatoire** : arbre de rang 1 avec spans et `rule_id` demontrant les bons parents pour la coordination, `to fancy`, `where`, `your mothers` et `that let ...` ; aucune solution fondee seulement sur `completed=true`.
- **Regression** : arbre historique du cas 359, phrase cible et voisins, qualite 120/120 et 24/24, smoke, tests complets, comparaison des 500 indices a budgets constants et CI verte avant toute comptabilisation.

**Decision revisee** : ne pas modifier les regles ni le lexique a ce stade ; garder 463 parmi les cas non resolus **et rouvrir le chantier**. La proposition dans [`MARKED_NONSTANDARD_USAGE_DESIGN.md`](MARKED_NONSTANDARD_USAGE_DESIGN.md) precise comment enregistrer un emploi volontairement non standard sur la relation sujet/copule, sans contaminer la grammaire. Remettre le curseur a `last_attempted_index=438` pour que la prochaine selection automatique retourne **463**. Le bilan de reference reste **474/500**, commit de code valide `aa49159dae957fca9c42aa870bfc614b7ef97ca3`. Aucun nouveau test global ni CI ne sont necessaires pour cette mise a jour purement documentaire.
