# Cas 463 — coordination négative, interrogative indirecte et relative extraposee

## Etat : structure complete en mode marque, score strict distinct

- Base de cette reprise : `449c55d7081a013cef5848fef2c07446ee2be9c1`.
- Cohorte gelee : SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- Livre : *Treasure Island* (Gutenberg 120), index **463**.
- Original : `You've neither sense nor memory, and I leave it to fancy where your mothers was that let you come to sea.`
- Analyse `QUOTE_BALANCED` : `"You've neither sense nor memory, and I leave it to fancy where your mothers was that let you come to sea."` (guillemets synthetiques, provenance et texte source inchanges).
- Budgets de diagnostic : `max_items=50000`, `kbest_work_limit=500000`; WordNet 3.0 existant.

## Diagnostic initial reproductible

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

Trois difficultes **independantes** ont ete isolees sans raccourci :

1. **Auxiliaire contracte / possession niee.** La matrice de `You've` contient `You` (`PRONOUN`, provenance `contraction-base`) et `'ve` (`HAVE`, provenance `contraction-clitic`). La regle transitive standard exige `V`, alors que `HAVE` est actuellement reconnu comme auxiliaire de parfait ou dans certaines constructions possessives typées. `You have neither sense nor memory.` est reconnu avec `VP/vp_transitive` et `NP/np_gerund_coord` ; `You've neither sense nor memory.` ne l'est pas. Une solution devra couvrir les possessifs contractes avec objet nominal coordonne negatif sans transformer arbitrairement tout `HAVE` en verbe lexical.
2. **Accord non standard explicite.** `your mothers` est nominal **pluriel** ; `was` est une copule **singuliere**. `where your mother was` se construit, mais `where your mothers was` non. Unifier de force `plural` et `singular`, modifier la graphie gelee ou forger une lecture lexicale de `mothers` serait une contamination. Une future prise en charge doit representer *l'accord dialectal* explicitement et le limiter a un contexte ou registre atteste, avec controles negatifs en anglais standard.
3. **Portee et attachement de la relative.** Dans la sequence `where your mothers was that let you come to sea`, `that let you come to sea` a pour antecedent `your mothers` ; elle n'est pas l'attribut nominal de `was`. Sur le temoin singulier `I leave it to fancy where your mother was that let you come to sea.`, l'arbre de rang 1 est **incorrect** : `NP/np_inf_rel` rattache `to fancy ...` a `it`, et `VP/vp_cop_np` prend `that let ...` comme attribut de `was` via `NP/np_wh_clause`. Il faut une construction structurelle pour la relative postposee ou extraposee, avec l'interrogative indirecte et le complement infinitif correctement rattaches au predicat principal.

Les temoins `I leave it to fancy where your mother was.` et `where your mother was that let you come to sea` possedent eux aussi des analyses dont les attaches ne sont pas acceptables. La completion de ces variantes n'est donc pas un critere de succes.

## Resolution structurelle et mode non standard

Le mode strict est conserve (`parse_corpus_case(parser, case)`), et le mode
marque doit etre demande explicitement par
`parse_corpus_case(parser, case, allow_marked_deviations=True)`. Une seule
entree publique de parsing est utilisee, `Parser.parse`. Les deux modes
conservent les guillemets transferes et les budgets de la cohorte.

L'arbre selectionne du mode marque est **complet** et ses attaches ont ete
verifiees par les identifiants de regles, enfants et spans :

| Segment de l'analyse | Regle selectionnee | Rattachement verifie |
| --- | --- | --- |
| `You've neither sense nor memory` | `vp_possessive_have_negative_correlative` et `np_negative_correlative_nor` | L'auxiliaire contracte `HAVE` est possessif; `neither N nor NP` est un groupe nominal negatif coherent. |
| `I leave it to fancy where ...` | `vp_complex_transitive_np_to_clausal_wh` | `it` est l'objet de `leave`; `to fancy` et l'interrogative sont des complements du predicat principal, pas du pronom. |
| `where your mothers was that let you come to sea` | `wh_clause_postposed_relative_marked_plural_subject_singular_copula` | `that let you come to sea` est la relative du sujet nominal `your mothers`, pas l'attribut de `was`. |
| Point final et guillemets | `dialogue_quote_clause_comma` | Le point final est conserve avec son span litteral entre `OPEN-QUOTE` et `CLOSE-QUOTE`. La lecture `COMMA` du point est un heritage du classement de ponctuation de dialogue, preserve ici pour ne pas regresser les arbres deja valides. |

Le **seul** ecart licencie sur l'arbre est un desaccord de nombre sur le lien
`subject_to_copula` : sujet `your mothers` **pluriel** en `[64,76)` de l'analyse
(source originale `[63,75)`), copule `was` **singuliere** en `[77,80)`
(original `[76,79)`). Il est enregistre par `UsageDeviation` avec
`kind=subject_copula_number_agreement`, `expected=plural`,
`observed=singular`, `register=literary_dialogue` et `intent=unknown`.
Ni les formes ni les traits lexicaux ne sont reinterpretes. Le guillemet
synthetique initial ne recoit **aucun** span dans l'original.

La regle marquee est dans `data/marked_usage_grammar.jsonl`, hors de la
grammaire standard. Elle n'est disponible que sur demande et dans le cadre
d'une citation; elle exige une interrogative, un sujet nominal pluriel en
troisieme personne, une copule finie singuliere et une relative de sujet
postposee. Ces conditions ne justifient **pas** `The sailors was.` comme
analyse complete : aucun assouplissement general de l'accord.

Les vues lexicales contextuelles `DET-NEG-CORR`, `HAVE-NEG-CORR` et
`V-COMPLEX-WH-INF` preservent les candidats d'origine du lattice et sont
activees seulement en presence de preuves syntaxiques locales. Elles sont
fondees sur les classes grammaticales et les traits, pas sur la citation
exacte ni sur un lexeme propre a cette phrase.

## Tests et garanties

- **Positifs independants** : une coordination `neither N nor N` avec `have` contracte et autre vocabulaire ; une relative de sujet extraposee sous interrogative indirecte avec sujet au singulier ; un temoin dialectal explicitement marque et independant de cette citation.
- **Negatifs** : `neither` sans `nor` ne doit pas autoriser la meme construction correlative ; le changement de nombre ne doit pas permettre `the mothers was` dans un contexte standard ; la relative ne doit pas pouvoir se rattacher a la copule comme attribut.
- **Cible obligatoire** : arbre de rang 1 avec spans et `rule_id` demontrant les bons parents pour la coordination, `to fancy`, `where`, `your mothers` et `that let ...` ; aucune solution fondee seulement sur `completed=true`.
- **Regression** : arbre historique du cas 359, phrase cible et voisins, qualite 120/120 et 24/24, smoke, tests complets, comparaison des 500 indices a budgets constants et CI verte avant toute comptabilisation.

Les nouveaux tests dans `tests/test_marked_nonstandard_usage.py` demontrent la
cible, les positifs independants (`You've neither patience nor courage.`,
`I leave it to imagine where the sailors were that let us go to sea.`),
le contraste de coordinations incorrectes et l'impossibilite d'obtenir le
meme ecart dans une phrase non citee. Le temoin historique 359 conserve son
arbre et ses budgets de reference. L'audit grammatical direct donne 120/120
positifs et 24/24 contrastes.

Le diagnostic integral de la cohorte de 500 phrases confirme **474/500** en
mode strict, comme avant. Les 500 statuts, indicateurs de saturation de foret
et limites k-best sont **identiques** a ceux du bilan initial, et le cas 359
conserve exactement `forest_nodes=1472` et `partial_states=48529`.
Le cas 463 demeure `roots_without_valid_analysis` dans l'evaluation stricte;
il devient complet **uniquement** dans le mode marque avec une deviation
structurale explicitement enregistree. Le commit de code est
`49384f5031f141981a0401bcedfceb41eb7cad26`.

**Comptabilisation** : le succes annote de 463 est **distinct** du bilan
canonique. La phrase reste dans la liste des cas non resolus **en analyse
stricte**; aucun point de couverture standard n'est attribue a un accord
non standard. Voir [`MARKED_NONSTANDARD_USAGE_DESIGN.md`](MARKED_NONSTANDARD_USAGE_DESIGN.md)
pour le contrat et le schema de l'annotation.
