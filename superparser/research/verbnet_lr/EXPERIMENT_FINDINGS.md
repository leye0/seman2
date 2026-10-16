# Seman2 / VerbNet L→R — bilan expérimental

**Branche :** `research/verbnet-left-to-right-poc`  
**Reproduction CI :** [GitHub Actions](https://github.com/leye0/seman2/actions/workflows/verbnet-lr-research.yml)  
**Résultats générés :** [reader_ablation.json](reader_ablation.json), [full_corpus_report.json](full_corpus_report.json)  
**Statut :** **POC de recherche ; aucune variante activée par défaut en production.**

## Ce qui a été effectivement exécuté

- Importation du corpus VerbNet 3.4 épinglé à `ae8e9cfdc2c0d3414b748763612f1a0a34194cc1`, avec index des sens WordNet 3.0.
- Compilation de **28 563** cadres pour **4 567** lemmes ; **6 678 / 6 776** clés WordNet distinctes reconnues.
- A/B/C/D/E/F/G sur **120 phrases distinctes** (50 dev, 50 validation, 20 holdout), **2 répétitions**, même dictionnaire et même grammaire.
- Exécution du **lecteur incrémental compilé** `SemanCompiledReader`, pas du parseur de production ni d'une forêt.
- Deux métriques différentes : *complétion* d'une phrase et *satisfaction de toutes les assertions syntaxiques explicitement annotées* (règles requises/interdites, POS, constituants). Cette dernière ne constitue **pas** une vérification exhaustive de l'arbre.

## Ablation intégrale

Les chiffres de réussite ci-dessous sont exprimés en **phrases uniques sur 120**, non en répétitions :

| Mode | Complétées | Assertions explicites satisfaites | Médiane totale (CI) |
| --- | ---: | ---: | ---: |
| A — baseline L→R | **44** | **35** | ~3,73 ms |
| B — VerbNet par lemme | 44 | 35 | ~3,81 ms |
| C — VerbNet par sens exact | 44 | 35 | ~3,77 ms |
| D — regard structurel 2 tokens | 55 | 34 | ~5,07 ms |
| E — 2 tokens + VerbNet exact | 55 | 34 | ~5,19 ms |
| F — regard structurel 3 tokens | 46 | 31 | ~4,46 ms |
| G — 3 tokens + VerbNet exact | 46 | 31 | ~4,53 ms |

Les temps dépendent de la machine GitHub Actions, du cache et de la charge ; ne pas les interpréter comme des latences de production ni comme une accélération démontrée.

Par split, les assertions explicitement satisfaites :

| Mode | Dev / 50 | Validation / 50 | Holdout / 20 |
| --- | ---: | ---: | ---: |
| A, B, C | **12** | **17** | **6** |
| D, E | 13 | 15 | 6 |
| F, G | 12 | 14 | 5 |

**Verdict : aucun GO.** VerbNet est rapide et reconnu, mais les points d'injection essayés ne changent aucune décision syntaxique. Le lookahead à 2 tokens augmente le nombre de complétions, **tout en faisant régresser les assertions**. Le lookahead à 3 tokens fait régresser davantage la qualité.

## Lecture structurelle des véritables arbres (nouvelle POC)

`tree_evidence.py` analyse après coup les **VP explicitement construits** par le lecteur : tête lexicale verbale, NP, complément en PP avec préposition, infinitif, etc. Il ne modifie aucune décision, ne construit aucun arbre supplémentaire et n'affirme jamais qu'un cas `UNKNOWN` est agrammatical.

Sur le **mode A**, parmi les 38 VP observés dans les arbres du premier passage :

- **32/38 attestés** par un cadre VerbNet aligné à un sens WordNet.
- **5/38 inconnus**, **1/38 préfixe seulement**.
- Parmi les 32 attestés, **30** appartiennent à une analyse satisfaisant les annotations syntaxiques et **2** à une analyse ne les satisfaisant pas. L'attestation du cadre ne prouve donc pas la justesse de l'arbre complet.
- Exemple positif : `Mary gave John a book.` produit `vp_ditransitive`, événements `NP NP`, attestés.
- Cas où **il ne faut surtout pas rejeter** : `Thomas offered Rachel a seat.` a une analyse `vp_ditransitive` conforme aux annotations, mais la projection VerbNet indique `UNKNOWN`.
- Autre limite concrète : `Either route seems safe.` a une analyse conforme aux annotations, mais la tête analysée a le lemme `seems`, qui ne correspond pas à l'index `seem` ; cela mérite une vérification morphologique générale, non une exception lexicale ponctuelle.
- Un cadre attesté peut accompagner une analyse erronée : `Peter sent Susan a message.` reçoit un cadre `NP NP` attesté, mais le choix `vp_obj_pred` ne satisfait pas toutes les contraintes explicites.

### Une conclusion architecturale importante

Il faut **distinguer les connaissances linguistiques des décisions de construction**. VerbNet contient une information exploitable et bon marché, mais son insertion comme minuscule bonus de candidat lexical est trop tardive et ne change pas les choix de branches. Un lookahead glouton plus fort fait souvent choisir une structure complète mais mauvaise.

La prochaine expérience pertinente devra comparer **plusieurs constructions grammaticalement licenciées au même point de décision**, sans développer une forêt globale : conservation temporaire de quelques *états de continuation* compacts, unification de contraintes sur preuves positives, décision retardée jusqu'au premier indice discriminant, puis vérification de la structure et des latences. Un arrêt par budget doit signaler `INCOMPLETE`, jamais une fausse agrammaticalité.

Il est prématuré d'ajouter une règle pour chaque exemple en échec. En particulier, ne pas modifier `grammar.jsonl` pour forcer les phrases du corpus ni sélectionner une variante grâce aux données holdout.

## Reproduire

Depuis la racine `seman2` :

```bash
PYTHONPATH=superparser .venv-popper/bin/python -m unittest discover -s superparser/tests -p 'test_verbnet*.py' -v
PYTHONPATH=superparser .venv-popper/bin/python -m unittest discover -s superparser/tests -p 'test_compiled_lookahead2.py' -v

PYTHONPATH=superparser .venv-popper/bin/python superparser/scripts/benchmark_verbnet_reader.py \
  --index superparser/research/verbnet_lr/verbnet34.compiled.json.gz \
  --max-cases 120 --repetitions 2 \
  --report superparser/research/verbnet_lr/reader_ablation.json
```

Le runner CI extrait WordNet 3.0 explicitement ; sur une autre machine, utiliser `--wordnet-dir /chemin/vers/dict` si `wordnet_path` est absent.

Toutes les options VerbNet et lookahead sont **désactivées par défaut** dans le lecteur expérimental ; le parseur de production `engine.py`/`vector_chart.py` est resté inchangé.
