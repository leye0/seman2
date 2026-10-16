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

## POC suivant : continuités grammaticales compactes (checkpoint borné)

**Exécution CI validée :** [suite comparative A–M](https://github.com/leye0/seman2/actions/runs/38851023890).
Une expérience séparée, **désactivée par défaut**, mémorise les positions
où plusieurs transitions sont autorisées par le trie grammatical. Lorsqu'une
lecture échoue ou s'arrête avant d'avoir consommé la phrase, elle peut tester
une alternative grammaticalement autorisée. Limites rigides : 0 à 6 reprises
programmables, **un seul arbre actif**, aucun chart, aucune forêt ni
fabrication de règles, arrêt explicite lorsqu'aucune reprise n'aboutit.

**Distinction importante :** ce POC fait une *relecture bornée depuis le début*
de la phrase. Il ne maintient pas encore simultanément plusieurs piles
incrémentales ni ne reprend une pile depuis un snapshot profond. Le coût
intégral de toutes les tentatives est inclus dans les mesures.

### Résultats des 120 phrases, 2 passages

| Mode | Complétions | Toutes les assertions explicites satisfaites | p50 total | p95 total |
| --- | ---: | ---: | ---: | ---: |
| A lecteur d'origine | 44/120 | 35/120 | 3,29 ms | 7,15 ms |
| K reprise paresseuse ×1 | 55/120 | 43/120 | 4,48 ms | 12,10 ms |
| M reprise paresseuse ×2 | 59/120 | 46/120 | 4,81 ms | 17,65 ms |
| L reprise paresseuse ×3 | **64/120** | **49/120** | 5,08 ms | 19,00 ms |

Les assertions sont la vérité terrain **partielle** du corpus : catégories POS,
constituants et règles explicitement annotés. **Leur satisfaction ne démontre
pas l'exactitude exhaustive de la structure.** Le corpus compte 50 phrases dev,
50 validation et 20 holdout. Entre A et L, il y a **14 gains et 0 perte**
selon ces assertions, avec les gains répartis sur les trois splits :
dev 12→20, validation 17→22, holdout 6→7.

### Résultat architectural

Contrairement au lookahead glouton, qui améliore la complétion tout en
détériorant la qualité, quelques reprises grammaticalement **bornées**
améliorent les deux métriques. VerbNet exact ne change toujours pas les
résultats : son rôle utile demeure l'attestation positive des cadres.

La variante « lazy » évite de chercher des alternatives pendant une lecture
qui réussit ; elle conserve les mêmes analyses que la version qui énumère
les alternatives immédiatement et est légèrement moins coûteuse dans
l'expérience. Le p95 à trois reprises demeure élevé à **19 ms**, notamment
parce que les préfixes de phrase sont relus. Le meilleur compromis mesuré pour
une cible médiane proche de 5 ms est actuellement **M (2 reprises)**, sans
que cela justifie son activation par défaut.

Des erreurs majeures subsistent, notamment la voix passive : une proposition
achevée avec un cadre copulatif adjectival peut encore manquer le
`clause_passive` exigé. Un parse terminé n'est jamais déclaré correct sur
la seule base de sa complétion.

### Utilisation expérimentale

```python
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader

reader = SemanCompiledReader.from_dir(
    "superparser/data",
    checkpoint_budget=2,
    lazy_checkpoints=True,
)
result = reader.parse("She did not open the window.")
print(result.complete, result.outcome.counters)
```

La compilation de la grammaire est faite à la création du lecteur.
Aucun effet sur `Parser` / `vector_chart.py`. Le paramètre
`checkpoint_budget=0` préserve le comportement du lecteur de référence.

**Étape suivante justifiée :** remplacer la relecture du préfixe par une
sauvegarde/restauration légère des continuations locales, en conservant les
mêmes budgets et assertions. Tester séparément les vraies négatives
grammaticales ; le corpus courant mesure surtout des phrases positives.

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

## Conformité grammaticale et objectif de latence (contrôle supplémentaire)

**Important : cette section remplace les interprétations optimistes plus haut.**
Les premières ablations ne vérifiaient pas la voix et le prédicat principal.
Les dernières mesures incluent désormais **voix, prédicat, règles requises et
interdites, parties du discours et constituants**, ainsi qu'un corpus de
**24 minimal pairs négatives**, séparé du corpus des 120 phrases positives.

**Exécution CI :** [analyse positive + négative validée](https://github.com/leye0/seman2/actions/runs/38852751384).
**Rapports :** [grammar_quality_gate.json](grammar_quality_gate.json),
[negative_report.json](negative_report.json),
[reader_ablation.json](reader_ablation.json).

| Mode | Conformités positives / 120 | Acceptations négatives / 24 | Médiane positives |
| --- | ---: | ---: | ---: |
| A — initial | 34 | 6 | 3,26 ms |
| N — 1 restauration locale | 41 | 9 | 3,79 ms |
| O — 2 restaurations locales | 44 | 13 | 4,03 ms |
| P — 3 restaurations locales | 45 | 16 | 4,20 ms |

**Décision : NE PAS ACTIVER N/O/P.** La médiane reste sous le **plafond
expérimental ciblé de 5 ms**, mais la qualité mesurée *sur les phrases négatives*
se dégrade fortement. Un test unitaire vert signifie que le banc d'essai
fonctionne ; il ne signifie pas que la variante franchit le **quality_gate**
du rapport. Les analyses acceptées mais non conformes passent de **10/120**
dans A à **23/120** dans P. Ces mesures tiennent compte de la lecture
complète et de la matérialisation, à chaud, sur runner GitHub ; ne pas
extrapoler à toutes les machines.

### Causes déjà observées dans les véritables arbres sélectionnés

1. `The boy are happy.` : le lexème `are` de catégorie `COPULA` peut
   être associé au trait **number=singular** dans les données lexicales.
   L'incompatibilité *surface ↔ traits* n'est pas suffisamment interdite.
2. `The books is heavy.` : un chemin `np_quant_n` laisse coexister
   `DET` singulier et nom pluriel sans propagation suffisante ;
   la tête `heavy` est en outre interprétée comme `ADV`.
3. `She should goes home.` : une construction modale sélectionnée
   n'exige pas suffisamment la morphologie **base** du verbe principal.
4. `She did not opened the door.` : la règle `clause_neg_vp` accepte
   un verbe au trait **finite** là où l'auxiliaire `did` requiert
   une base verbale.
5. `They donated John a book.` : un cadre `vp_obj_pred` reste
   licencié sans vérifier que cette alternance ditransitive est
   autorisée par le sens verbal correspondant. L'absence d'un cadre
   VerbNet ne constitue toutefois **pas** une preuve négative suffisante.

Le même problème ne se résout pas en accumulant des listes de phrases
exceptionnelles. **Prochaine étape architecturale :** une couche déclarative
de **contraintes obligatoires de construction**, alimentée par les traits
morphologiques corrects et appliquée avant l'acceptation finale ;
puis A/B sur les **120 positives + 24 négatives**, avec seuil de
**médiane ≤ 5 ms**, **aucune nouvelle acceptation négative**, et **aucune
régression d'assertion positive**. Les erreurs grammaticales du corpus
holdout ne doivent pas servir à choisir des règles ajustées à ces phrases.

Le lecteur à restaurations locales reste un excellent mécanisme de
**recherche bornée**, mais il ne doit pas servir de substitut aux contraintes
linguistiques. Les négatives mal classées ne sont pas déclarées
« grammaticales » ; une lecture incomplète ne prouve pas non plus
l'agrammaticalité.

## Itérations : garde morphosyntaxique, test négatif et généralisation externe

**CI vérifiée :** [A/B conformité + performance](https://github.com/leye0/seman2/actions/runs/38855212291).
Les chiffres ci-dessous proviennent du lecteur expérimental, à chaud, et ne
représentent ni un parseur de production ni une exactitude de dépendances UD.

### Vérification stricte des 120 positives et 24 négatives

| Variante | Assertions positives / 120 | Fausses acceptations / 24 | Médiane |
| --- | ---: | ---: | ---: |
| Baseline | 34 | 6 | 4,40 ms |
| Garde, zéro reprise | 34 | **1** | **4,47 ms** |
| Garde, une reprise locale | 41 | **1** | 5,14 ms |
| Garde, trois reprises locales | **46** | **1** | 5,84 ms |

La variante **garde sans reprise** passe à la fois les conditions de
non-régression positive, de non-aggravation des négatives et de médiane
**≤ 5 ms**. Les variantes à reprises passent les contrôles de qualité
partiels, mais dépassent le seuil strict de médiane observé sur ce runner.
Le contrôle est volontairement une double barrière : un parse qui termine
mais viole la morphologie ou les assertions ne compte pas comme bonne
analyse.

Garde implémenté dans [construction_guard.py](construction_guard.py),
**désactivé par défaut**, couvrant des familles productives : accord de
`be`/`have`/`do` avec sujet clairement identifié, singulier/pluriel
de déterminants clairement identifiés, forme de base après modal/do,
et construction verbale à prédicat objet. La forme `V base` doit aussi
être compatible avec la surface écrite. Les homographes modaux sont
identifiés depuis les **candidats du lexique**, pas depuis des phrases de
test. Les cas sans preuve morphologique suffisante restent non tranchés.

### Longues phrases : ne pas confondre temps d'arrêt et analyse réussie

Le corpus stress [long_sentence_stress.jsonl](long_sentence_stress.jsonl)
contient 8 phrases manuellement composées, de **31 à 65 mots**, sans arbre
gold. Aucune n'est encore complétée, y compris avec trois reprises locales.
Le coût médian total du lecteur initial est ~17,2 ms, dont ~8,7 ms
d'ingestion lexicale, et le lecteur à trois reprises ~19,2 ms. Aucun exemple
ne passe le cap de 75 % des tokens selon le rapport initial. Une faible
latence d'arrêt n'est donc **pas une preuve de parsing efficace des longues
phrases**.

Un accélérateur expérimental pour les recherches multiword
[fast_lattice.py](fast_lattice.py) conserve exactement les décisions du
lecteur initial sur les 120 cas de référence, mais le gain mesuré (~4,40 →
~4,37 ms sur les phrases courtes) est faible et du niveau du bruit de mesure.
Il reste expérimental.

### Généralisation hors corpus Seman2 : UD English-EWT

Le banc [benchmark_ud_ewt_lr.py](../../scripts/benchmark_ud_ewt_lr.py)
utilise la révision externe épinglée
`4a4d77f599ea53cc405f85d0cec4b2f14f81d42b` du corpus
[Universal Dependencies English EWT](https://github.com/UniversalDependencies/UD_English-EWT),
avec un échantillonnage déterministe indépendant des sorties du parseur
(8 phrases chacune des bandes **8–14, 15–24, 25–39 et 40–70 mots**).
Le baseline n'en complète **aucune sur 32** ; la variante à trois reprises
avec garde en complète **une sur 32**, sans alignement complet aux tokens gold
sur lequel calculer une qualité POS. Cela signale que les gains observés
sur les phrases construites du projet **ne se généralisent pas encore**.
On ne peut donc pas parler de bonne couverture grammaticale générale.

**Priorité structurelle:** poursuivre les tests des contraintes générales
en conservant des lectures alternatives compactes, mais surtout accroître
la couverture des propositions relatives, enchâssées et coordonnées.
Éviter de faire de l'optimisation du p50 pour un lecteur qui échoue trop tôt
sur les vraies phrases. Réserver les exemples holdout/UD aux contrôles
externes, pas à des règles spécifiques.

**Cette note est un état de recherche, pas un GO de fusion vers main.**
