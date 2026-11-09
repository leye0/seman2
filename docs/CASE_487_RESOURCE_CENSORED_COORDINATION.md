# Cas 487 — coordination finie après un complément temporel antéposé

**Statut : bloqué, non corrigé.** Ne pas transformer la présence d'une racine
symbolique ou la réussite d'une sous-phrase en succès grammatical du cas.

## Provenance et budget de référence

- Cohorte fixe : `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- Base canonique : commit de code `5b757eb329ab706ef082a939f070d3dad9ee97af`,
  [diagnostic de 500 phrases](https://github.com/leye0/seman2/actions/runs/42527736728)
  : **474/500**. Le commit documentaire de départ est `f2642aa4a5131ce12826614bafd78a6cf22b73fc`.
- Diagnostic ciblé : commit `f5a5a266c046c90b67828d7e34136a3b6acecafe`,
  [CI verte](https://github.com/leye0/seman2/actions/runs/42544413611),
  artefact `residual-grammar-validation`, journaux `case487-full-audit.log` et
  `case487-constituents.log`.
- Même `Parser.parse` public, WordNet 3.0, cohorte `QUOTE_BALANCED`,
  `max_items=50_000`, `kbest_work_limit=500_000`, sans élever les budgets ni
  toucher aux règles. Le cas complet passe exclusivement par `parse_corpus_case`.
- Index 487, livre 120, identifiant `120:afdbd6a1f4cd33e6` :

  > the most part of the time we were broadside on, and I am very sure I never should have made the ship at all but for the tide.

  C'est la seconde partie, séparée par un point-virgule, de la phrase source
  « She turned in every direction but the one I was bound to go; the most
  part of the time ... ». Aucun préfixe synthétique n'est injecté.

## Constats mesurés

| Analyse | Complète | Nœuds | États partiels | Arbre sélectionné |
| --- | --- | ---: | ---: | --- |
| Cas canonique 487 | non, forêt saturée | 1 560 | 48 440 | aucun |
| `the most part of the time we were broadside on` | non, sans saturation | 287 | 7 734 | aucun |
| `we were broadside on` | oui | 59 | 1 577 | `clause_np_vp` |
| `I am very sure I never should have made the ship at all but for the tide` | oui | 613 | 19 629 | `clause_np_vp` |
| `I never should have made the ship at all but for the tide` | oui | 365 | 11 474 | `clause_np_vp` |
| `I am very sure` | oui | 46 | 1 165 | `clause_np_vp` |

Les sous-phrases sont des **probes locaux indépendants** : elles ne remplacent
pas le cas Gutenberg, ne sont pas des changements de cohorte et ne prouvent
pas l'analyse globale. Le diagnostic lexical canonique contient **150
candidats** et aucun mot privé de candidat. La forêt complète contient une
racine structurale, mais celle-ci n'a pas produit d'arbre validé dans le
budget. `partial_proposals=59_585`, `kbest_work_units=15_389` ; le problème
rapporté n'est pas une saturation de k-best.

Les premières familles par états partiels dans la forêt saturée sont notamment
`clause_np_v_np_adjp` (802), `clause_vp_adv_conj` (693),
`clause_object_topicalization_modal` (664), `np_rel_pp_strand` (654) et
`np_part_ed_name`, `np_part_ed_obj`, `np_part_ing` (631 chacune). Les catégories
dominantes sont `CLAUSE` (20 438) et `NP` (18 238). Ces **comptages décrivent**
la saturation : ils n'établissent pas qu'une de ces règles est incorrecte.

## Isolations des constituants et attaches

Le noyau gauche a une analyse claire :

```text
CLAUSE clause_np_vp [0:20] we were broadside on
  NP np_indef_pron [0:2] we
  VP vp_cop_adj_adv [3:20] were broadside on
    COPULA were | ADJ broadside | ADV on
```

La chaîne entière de gauche ne réussit cependant **pas** à joindre le groupe
antéposé `the most part of the time` à cette proposition. C'est un sous-blocage
de composition syntaxique observable sans censure ; il reste à établir si la
cause exacte est la projection temporelle du NP, la combinaison propositionnelle
ou les contraintes des règles existantes.

Le code de `engine.py` possède déjà `_binary_coord_clause_plan` pour une seule
virgule suivie d'un coordonnant et de deux débuts de proposition explicites.
Le cas 487 satisfait ces indices de surface (`the ... , and I ...`), mais
`_parse_hierarchical` exige que **chaque segment** réussisse. Le segment
gauche échouant, le parseur revient à la forêt globale, où il sature.
**Inférence d'après la logique actuelle du code et les probes**, et non preuve
qu'il suffirait d'assouplir le garde-fou de la décomposition.

La droite complète présente un second obstacle de **qualité**. Son arbre de
rang 1 rattache :

```text
VP vpnp_base_perfect_transitive
  HAVE have | V made
  NP np_pp_mod [40:72] the ship at all but for the tide
    NP np_det_n [40:48] the ship
    PP pp_adv_prep [49:72] at all but for the tide
      ADV at all
      PP pp_adv_prep [56:72] but for the tide
```

Or `at all` porte sur la négation / le prédicat verbal et `but for the tide`
est un complément exceptif causal dans cette lecture, **pas** une propriété
nominale du navire. La proposition droite est donc « reconnue » mais le
rattachement sélectionné est insatisfaisant. Il serait incorrect de promouvoir
le cas 487 à `completed` grâce à la seule décomposition.

## Verdict et prochaine investigation

**Aucune règle, entrée lexicale, limite de calcul ou politique de classement
n'a été modifiée.** Le score canonique reste au dernier bilan vérifié de
**474/500**, et le cas 487 conserve le statut `forest_budget_exceeded` dans la
file. Le témoin 359 a été audité dans la même CI ; il demeure `completed=True`
en mode `dialogue_unattributed`, malgré une saturation observée dans son
parcours interne. Aucun arbre cible 487 n'a été certifié, donc aucune
régression structurelle ne peut encore être comparée pour ce cas.

Pour un futur passage sur 487, isoler de façon compositionnelle et contraignante
les NP temporels antéposés (`the greater part of the day`, `the whole night`,
etc.), avec exemples positifs indépendants et contrastes négatifs ; puis
vérifier l'attache *verbale* de `at all` et `but for ...`. Tester **l'arbre de
rang 1** du cas complet, le témoin 359, les 120 annotations et les 500 statuts
avant de revendiquer un succès. Ne pas augmenter les budgets, inventer une
exception pour cette citation ou supprimer l'ambiguïté lexicale pour gagner
un point.

Le curseur déterministe est avancé à **487** ; le cas reste non résolu et sera
revisité après un tour de file. Le prochain cas non résolu est **491**.
