# Seman2 — exécuter et comprendre LE Layer 1 actuel

**SOURCE DE VÉRITÉ du dépôt `leye0/seman2`, branche `main`.**
Ce fichier prime sur les anciens comptes rendus de recherche. Il est conçu pour un développeur ou un nouvel agent ChatGPT n'ayant lu aucune conversation antérieure.

## 1. Une seule architecture prise en charge

Seman2 est actuellement un **parseur grammatical symbolique anglais (Layer 1)** qui conserve le texte original, les spans et mots, les candidats lexicaux et leurs sous-catégories/traits, et restitue, quand elles existent, des analyses syntaxiques alternatives. Des recettes de relations sémantiques peuvent interpréter ces arbres; **le Layer 2 d'identités, mémorisation et apprentissage n'est PAS implémenté**.

Il y a exactement **DEUX moteurs de reconnaissance**, et pas davantage :

- **Canonique, par défaut.** `Parser(...)` → `Parser.parse(text)` → réseau lexical `segmentation.build_lattice` → `VectorGrammar.parse_lattice` → `_VectorForest.recognize` → `_LazyMaterializer` → `ParseResult`.
- **Adaptatif, explicitement opt-in.** `Parser(..., complexity_policy=ComplexityPolicy(...))` → même réseau lexical → `StructuralRiskRouter.choose` AVANT reconnaissance. **Court texte** (moins de `min_tokens`, 17 dans la recherche) : canonique **sans calculer le risque**. **Risque en dessous du seuil** : canonique. **Longue phrase non citée au-dessus du seuil** : `VectorGrammar(lazy_trie_recognition=True)` → `LazySharedTrieForest` → projection paresseuse des dérivations originales vers le MÊME `_LazyMaterializer`.
- **Dialogues / guillemets** : `dialogue.py` et la grammaire de dialogue dédiée sont conservés. Le trie adaptatif n'est **pas** utilisé pour eux tant que leur équivalence n'est pas prouvée.

L'option adaptative **n'est pas activée par défaut**, car les forêts atteignant le plafond de recherche ne bénéficient pas encore d'une preuve complète de fidélité. La performance globale de **−15,6 % de CPU** sur une cohorte historique de 128 phrases ne démontre pas un gain universel ou une validation de toutes les saturations.

## 2. Modules À MODIFIER (et seulement ceux-ci pour ce sujet)

| Chemin | Responsabilité |
| --- | --- |
| `superparser/seman_parser/runtime_gc.py` | Activation unique de `gc.freeze()` après chargement WordNet; garde-fous et variable de désactivation sans changer le parseur |
| `superparser/seman_parser/engine.py` | `ParserResources`, `Parser`, entrée `parse`, dialogues, routage, budgets, sortie `ParseReport` |
| `superparser/seman_parser/segmentation.py` | Tokenisation, `LexicalLattice`, toutes les lectures / sous-types / offsets |
| `superparser/seman_parser/vector_chart.py` | Grammaire compilée, forêt canonique, analyses multiples et `k-best` commun |
| `superparser/seman_parser/complexity_routing.py` | Calcul PRÉPARSE des débuts de règles; court-circuit court / dialogue; politique opt-in |
| `superparser/seman_parser/shared_trie_forest.py` | Compilation de l'automate de préfixes + agenda partagé de reconnaissance, infrastructure du trie lazy |
| `superparser/seman_parser/lazy_trie_forest.py` | Le SEUL moteur lourd retenu : états partagés, identifiants virtuels, projection des dérivations à la demande |
| `superparser/seman_parser/dialogue.py` | Marquage conservateur des guillemets sans effacer le texte |
| `superparser/seman_parser/sentence_boundaries.py` | Segmentation de prose/romans et abréviations |
| `superparser/seman_parser/chart.py`, `features.py`, `grammar.py`, `lexicon.py`, `lexicon_from_wordnet.py`, `wordnet.py`, `syntax.py`, `semantic_rules.py`, `semantics.py`, `symbols.py`, `types.py` | Contrats de données, grammaire, morphosyntaxe, traces lexicales et sémantiques |

Le fichier `shared_trie_forest.py` n'est **pas un second moteur à choisir** : il constitue uniquement la base utilisée par `LazySharedTrieForest`.

### Gestion du garbage collector CPython

En exploitation, Seman2 appelle automatiquement `gc.freeze()` **une seule fois par processus** une fois les quatre parties principales des données WordNet chargées, au début d'un parsing et avant toute nouvelle forêt grammaticale. Le GC reste activé. Cette politique est **indépendante** de la complexité grammaticale et n'active aucun autre moteur. Les ressources sans WordNet et les exécutions où le GC est désactivé n'activent pas cette opération. Désactiver pour une application hôte qui gère elle-même ses objets : `SEMAN2_DISABLE_GC_FREEZE=1` avant le démarrage.

Ce gel reste **global au processus** et n'est pas sélectif sur les seuls objets WordNet. Voir le [benchmark de 1 000 phrases](GC_CPU_1000_SENTENCES_BENCHMARK_2026_10_18.md) pour la mesure, ses conditions de préchauffe et les limites de durée de vie / mémoire. Les outils expérimentaux ont été supprimés de `main`, mais sont disponibles dans l'historique Git de l'audit.

## Couche grammatico-structurelle entre segmentation et parsing

Le pipeline est explicitement : **texte → découpage typographique
(`split_prose_sentences`) → analyse structurale légère
(`structural_units.review_semicolon_boundaries`) → unités avec transfert de
citations → `parse_corpus_case` → `Parser.parse`**.

Cette passe intermédiaire ne construit **aucun arbre grammatical** et ne
consomme ni WordNet ni les budgets du parseur. Pour chaque point-virgule,
elle détermine s'il sépare deux propositions autonomes ou s'il coupe un
constituant dépendant (relative, participiale, infinitif coordonné, prédicat
à sujet partagé, antithèse elliptique `on one side…; on the other…`, série
de compléments prépositionnels préposés, `for` causal). Chaque décision
rend un motif explicite. L'absence de preuve entraîne le maintien de la
frontière, pas la création d'une règle de grammaire artificielle.

Deux instruments d'audit distincts :

- `scripts.audit_corpus_segmentation` mesure les liens reconnus par motif,
  la conservation des caractères sources et les altérations d'espacement;
  il ne certifie pas la syntaxe des arbres.
- `scripts.audit_fragment_grammar_rules` inspecte les **productions
  potentiellement permissives** apparues ou maintenues depuis la référence
  du 11 octobre 2026. Un drapeau `ellipsis` ou `CLAUSE` sans prédicat
  apparent **n'est pas une preuve de mauvaise règle** : les impératifs et
  certaines ellipses littéraires sont légitimes. Aucun retrait automatique.

## Découpage de romans et référence actuelle

**Une seule segmentation active**, sans bascule v1/v2 : les fonctions
`split_prose_sentences`, `split_analysis_units`,
`split_prose_analysis_units`, `gutenberg_novels.analysis_units` et
`extract` utilisent le découpage conservateur qui garde les relatives
supplémentaires, les prédicats partageant leur sujet, les listes participiales
et certaines citations imbriquées. Les deux représentations (texte source et
texte d'analyse à guillemets équilibrés) ont les **mêmes frontières**.
`parse_corpus_case` est obligatoire pour les études grammaticales.

- Benchmark **courant** : `scripts.diagnose_novel_parses` sélectionne
  500 unités du corpus nettoyé avec cet algorithme.
- Son SHA est versionné dans `docs/CURRENT_COHORT.json` : toute modification
  des frontières exige une nouvelle signature, une nouvelle file de cas et
  un **nouveau point de départ**, pas une prétendue amélioration de l'ancien score.
- `scripts.rebuild_grammar_case_queue` régénère les indices résiduels depuis
  les 500 résultats actuels. `next_grammar_case` les lit, jamais les
  numéros gelés des anciens diagnostics.
- Le test d'intégrité du corpus valide les guillemets, la conservation des
  caractères source et les cas adverses de segmentation. L'exactitude des
  **arbres grammaticaux** se mesure séparément.
- Les anciens diagnostics `475/500`, `cf58d1...` et leurs indices de
  phrases sont des **archives historiques**, conservées dans Git. Aucun
  mode de découpage historique n'existe dans la production.

## 3. Exécution depuis la RACINE du dépôt

**Pré-requis** : Python 3.12+ et un répertoire **WordNet 3.0 `dict/`** incluant `index.verb`, `data.verb`, `index.noun` etc. Ce répertoire externe n'est pas versionné. Voir la CI `.github/workflows/core-seman2-validation.yml` pour la procédure déterministe de téléchargement depuis l'archive WordNet de NLTK.

```bash
git clone https://github.com/leye0/seman2.git
cd seman2

export WORDNET_DICT=/chemin/vers/wordnet3/dict

# Commande de vérification PRINCIPALE : les trois routes réellement supportées.
WORDNET_DICT="$WORDNET_DICT" PYTHONPATH=superparser python -m scripts.smoke_layer1

# Tests du moteur, y compris les corpus nettoyés et les dialogues.
WORDNET_DICT="$WORDNET_DICT" PYTHONPATH=superparser python -m unittest -v \
  superparser.tests.test_parser_integration \
  superparser.tests.test_features \
  superparser.tests.test_data \
  superparser.tests.test_complexity_routing \
  superparser.tests.test_shared_trie_forest \
  superparser.tests.test_dialogue_grammar \
  superparser.tests.test_vector_chart \
  superparser.tests.test_layer1_output_contract \
  superparser.tests.test_clean_novel_corpus
```

La CI exécute ces tests et d'autres tests grammaticaux. **Une commande échouant dans la CI signifie que le ménage n'est pas terminé.** Ne pas déclarer la branche propre à moins qu'elle soit verte.

### Analyser une phrase par le chemin canonique (comportement par défaut)

```bash
WORDNET_DICT="$WORDNET_DICT" PYTHONPATH=superparser python - <<'PY'
import os
from seman_parser.engine import Parser, ParserResources

resources = ParserResources.from_dir(
    "superparser/data", wordnet_dict=os.environ["WORDNET_DICT"])
parser = Parser(resources)
report = parser.parse("John opened the box.")
print("completed:", report.result.completed)
tree = report.result.best()
print(tree.as_dict() if tree else None)
print("texte préservé:", report.result.text)
PY
```

### Démontrer le routage adaptatif — RECHERCHE UNIQUEMENT

```python
from seman_parser.engine import Parser, ParserResources
from seman_parser.complexity_routing import ComplexityPolicy

# Seuil 1 délibérément permissif pour FORCER le chemin trie dans un TEST;
# CE N'EST PAS UN SEUIL DE PRODUCTION CALIBRÉ.
parser = Parser(
    resources,
    complexity_policy=ComplexityPolicy(
        rule_start_threshold=1,
        min_tokens=17,
        difficult_strategy="trie",
    ),
)
report = parser.parse("John opened the box.")
# Courte : route canonique, sans même calculer le score préparse.
```

Une application qui n'a pas sélectionné / calibré de seuil DOIT utiliser le constructeur `Parser(resources)`, sans politique. Il n'existe **aucun** modèle de seuil universel approuvé.

## 4. Benchmarks et qualité

- Benchmark *du seul routage actuel*, sans le vieux code de comparaison des approches abandonnées : `superparser/scripts/benchmark_adaptive_routing.py`. Cohortes reproductibles de Gutenberg : `superparser/scripts/corpus_samples.py`.
- Exécution manuelle GitHub Actions : `.github/workflows/layer1-adaptive-benchmark.yml`. Ne pas lancer à chaque push (minutes CI).
- Corpus et ponctuation : `.github/workflows/clean-novel-corpus-ci.yml` et `.github/workflows/dialogue-grammar-regressions.yml`.
- Grammaire : `.github/workflows/direct-grammar-validation.yml`.
- Validation principale, **source de vérité des commandes** : `.github/workflows/core-seman2-validation.yml`.
- Tests essentiels : `test_complexity_routing.py`, `test_shared_trie_forest.py`, `test_layer1_output_contract.py`, `test_dialogue_grammar.py`, `test_vector_chart.py`, `test_sentence_boundaries.py`.

Limites : les phrases longues peuvent saturer la forêt; une saturation n'est pas « agrammatical ». Le `k-best` ne garantit pas une interprétation humaine correcte. Les traits, `requires`, contextes et ambiguïtés doivent rester intacts. Pour les forêts saturées, la parité complète entre reconnaisseurs **n'est pas encore certifiée**. NE PAS augmenter la couverture en comptant un groupe partagé comme un seul état sous l'ancien plafond de 20 000.

## 5. Données : NE RIEN EFFACER

- `superparser/data/` : règles grammaticales, fonctions, lexiques, traits, recettes sémantiques, grammaire des dialogues.
- `data/` : ressources et corpus suivis par ce dépôt.
- `superparser/research/verbnet_lr/corpora/` : quatre romans Gutenberg nettoyés (David Copperfield, Pride and Prejudice, Frankenstein, Treasure Island) **avec leurs guillemets originaux préservés**, plus un manifeste d'intégrité.
- `superparser/research/verbnet_lr/clean_novel_corpus.py` et `gutenberg_novels.py` : chargeurs et échantillonnage utilisés par le chemin de qualité.

Le corpus Wikipédia mentionné dans nos discussions **n'avait pas de fichier identifié dans l'arbre Git suivi** : aucune suppression de ce corpus n'est revendiquée. Ne jamais supposer qu'il est inexistant hors Git.

## 6. Ce qui a été ABANDONNÉ (aucun code dans `main`)

Ne réintroduire **aucune** implémentation historique simplement parce qu'un document ancien mentionne un benchmark prometteur :

- `online_prefix_edges`, `flat_prefix_edges`, `prefix_edges.py` : partage d'objets coûteux, sans gain net.
- `indexed_recognition`, stockage de clés entières : suppression de comparaisons bon marché, gain net non établi.
- `shared_trie_recognition` avec projection **eager** de toutes les règles : battu par le trie **lazy**, seul chemin retenu.
- `early_lexical_filter`, `cache_boundaries` : variantes A/B non conservées.
- `full_structure_snap`, cache de signatures / `subtree_feature_replay` : correspondances peu chères, mais aucune **accélération démontrée** et faux positifs possibles si acceptation directe.
- anciens systèmes GLR, C/hybrides, reading kernel, prévisions/induction, extraction de coréférence et discours : hors sujet du Layer 1 actuel.

L'ancien code est récupérable dans la branche explicitement sauvegardée **[`archive/pre-simplification-2026-10-18`](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18)** et dans l'historique Git. **Ne PAS garder des copies exécutables d'anciens moteurs dans `main`.**

## 7. Pour reprendre dans une nouvelle conversation

Dire : « Ouvre `leye0/seman2` sur `main`, lis **`docs/RUN_CURRENT_LAYER1.md`** puis `docs/CURRENT_RESEARCH_HANDOFF.md`, vérifie que le smoke et la CI passent. Le SEUL parcours actuel est `Parser` canonique ou, sur politique préparse opt-in, `LazySharedTrieForest` pour le texte difficile non cité; dialogues canoniques. Les anciens codes sont archivés et ne doivent pas être réintroduits. Prochaine étape : améliorer la correction et la couverture grammaticale en préservant tous les mots et toutes les alternatives, pas rechercher de nouveaux patterns d'optimisation. »
