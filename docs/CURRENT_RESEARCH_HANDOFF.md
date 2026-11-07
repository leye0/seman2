# Point de reprise — AGENT ChatGPT, commencer ici

**Dépôt privé : `leye0/seman2`, branche de travail `main`.**
**SOURCE TECHNIQUE ABSOLUE : [`RUN_CURRENT_LAYER1.md`](RUN_CURRENT_LAYER1.md).**
**PROTOCOLE OBLIGATOIRE DE CORRECTION D'UNE PHRASE : [`GRAMMAR_CASE_FIX_PROTOCOL.md`](GRAMMAR_CASE_FIX_PROTOCOL.md).**
Ce document est un aide-mémoire humain; si un ancien compte rendu contredit le code actuel ou RUN_CURRENT_LAYER1, vérifier `main` et suivre ce dernier.

## Ce que nous construisons

Un **Layer 1 grammatical anglais symbolique** qui préserve toutes les lectures / sous-types lexicaux, les mots, leurs spans, traits, règles, variantes et sorties syntaxiques pour un Layer 2 futur. Nous développons la couverture et la correction sur phrases de romans, dialogues, accords et cas lourds. **Le Layer 2 cognitif, les anciens moteurs de coref/discours et les prototypes de snapping ne font pas partie du code présent.**

Le propriétaire a explicitement demandé de **cesser pour le moment les optimisations avec de nouvelles approches et patterns**. Ne pas réintroduire d'anciens algorithmes ou recommencer les mêmes benchmarks sans demande.

## Chemin actuel — ne pas s'y tromper

- **Défaut :** `seman_parser.engine.Parser(resources)` → `segmentation.build_lattice` → `vector_chart.VectorGrammar` → `_VectorForest` → `_LazyMaterializer`.
- **Opt-in pour phrases complexes :** `Parser(resources, complexity_policy=ComplexityPolicy(rule_start_threshold=...,min_tokens=17))` → `complexity_routing.StructuralRiskRouter` AVANT parse. Si phrase courte ou score insuffisant : le **même canonique**. Sinon : `vector_chart.VectorGrammar(lazy_trie_recognition=True)` → `lazy_trie_forest.LazySharedTrieForest` utilisant `shared_trie_forest.TrieRecognitionBase`, avec le **même k-best**.
- **Dialogues/guillemets :** grammaire de dialogue séparée conservée, jamais confiée au trie tant que non certifié.
- `shared_trie_forest.py` est une **base du trie lazy**, pas un mode alternatif eager.
- **Seule stratégie lourde exposée : `trie`**. `online`, `flat`, `indexed`, `shared_trie_recognition`, `early_lexical_filter`, `cache_boundaries` sont supprimés. Ne pas chercher ou ajouter ces options.

## Exécution et tests EXACTS

Lire et exécuter la section « Exécution depuis la racine » de `docs/RUN_CURRENT_LAYER1.md`. La CI `.github/workflows/core-seman2-validation.yml` télécharge WordNet 3.0, exécute les tests **réels** puis `python -m scripts.smoke_layer1`. Pour accéder au `WORDNET_DICT` hors CI, utiliser un répertoire de dictionnaire WordNet 3.0 `dict`.

```bash
WORDNET_DICT=/chemin/wordnet3/dict PYTHONPATH=superparser python -m scripts.smoke_layer1
```

Après chaque modification : tester le chemin canonique, le chemin trie configuré, les dialogues, le contrat d'output, les guillemets et la morphosyntaxe. **Un changement de nombre d'arbres, de mots, de traits ou de budget n'est pas automatiquement un gain.** Ne pas traiter les forêts saturées comme une validation complète.

## Données protégées

Les quatre romans nettoyés sont dans `superparser/research/verbnet_lr/corpora/`; leur manifeste et les guillemets sont préservés. `superparser/data/` et `data/` sont conservés. Les fichiers de corpus Wikipédia mentionnés autrefois n'ont pas été identifiés parmi les fichiers suivis : ne pas prétendre les avoir supprimés ou les inventer.

## Historique à connaître, pas à exécuter

Le moteur adaptatif à préfixes partagés a démontré **−15,6 % de CPU** sur une cohorte de 128 phrases (Action [39177896708](https://github.com/leye0/seman2/actions/runs/39177896708)). Les alternatives `online`/`flat` et la variante `indexed` n'ont pas montré de gain net. Les caches de signatures de sous-arbres ont trouvé des correspondances rapides mais **aucune accélération supplémentaire mesurée** et comportaient des risques si l'on acceptait des formes sans revalider les traits. Les forêts saturées restent une incertitude de correction. Les scripts et sources de ces essais sont disponibles **uniquement dans la sauvegarde Git** [`archive/pre-simplification-2026-10-18`](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18) et dans les commits antérieurs.

Le dépôt courant a été nettoyé pour contenir uniquement le parseur grammatical retenu, ses tests de qualité, les données et un benchmark du chemin actif.

## Dernier jalon de correction (cas 480)

- Commit de code validé localement : `08a5aecef12457e72c97776380bfd6e200d04752` ; voir [`CASE_480_MARKED_REPORTED_DIALOGUE.md`](CASE_480_MARKED_REPORTED_DIALOGUE.md).
- Le cas **480** est un dialogue rapporté à deux incises dialectales (`says they` et `they says`). En mode explicite `allow_marked_deviations=True`, le meilleur arbre est entièrement structuré : thème `As for you`, adresse `Benjamin Gunn`, présentative `here's a musket`, puis liste nominale coordonnée elliptique, avec **deux écarts d'accord indépendants** et leurs offsets. En mode strict le cas reste incomplet et `intent=unknown` : aucune prétendue normalisation du dialecte.
- Les règles `SPEECH-TAG` ordinaires vérifient désormais les accords en nombre et en personne ; les écarts n'apparaissent que sous règles marquées avec provenance précise. Les deux ouvertures lexicalement typées de fragments préservent strictement le témoin de saturation **359** (arbre correct, **1472** nœuds / **48529** états).
- CI principale [42381648511](https://github.com/leye0/seman2/actions/runs/42381648511) et CI dialogue [42381648518](https://github.com/leye0/seman2/actions/runs/42381648518) **vertes**. Suite locale : **499 tests** réussis ; qualité **120/120**, contrastes **24/24**, faux négatifs acceptés encore **9/24** ; smoke vert. Cohorte stricte **474/500**, aucun nouveau changement de statut ou de budget. Les seuls changements par rapport à l'ancien snapshot du cas 463 sont les ajustements **466** et **473**, déjà établis au jalon précédent.
- Prochaine phrase déterministe selon `GRAMMAR_CASE_QUEUE.json` : **487**. Le cas **480** reste dans la file stricte pour une future discussion des usages marqués, sans inflation artificielle du score.

## Prochaine tâche SANS instruction supplémentaire

Améliorer la **couverture grammaticale et la justesse des analyses du Layer 1** sur les phrases qui échouent, en restant compatible avec les mots, traits, alternatives et les dialogues. Pour chaque phrase, **appliquer le protocole de correction** : inspecter l'arbre sélectionné et les rattachements exacts, faire des tests positifs ET négatifs, mesurer les régressions sur la cohorte figée et ne pas assouplir globalement des contraintes pour faire croire à des succès.

## Phrase de reprise

> « Continue Seman2 sur `main`. Lis `AGENTS.md`, `docs/RUN_CURRENT_LAYER1.md`, `docs/CURRENT_RESEARCH_HANDOFF.md` et, pour toute correction de phrase, `docs/GRAMMAR_CASE_FIX_PROTOCOL.md`. Seuls le canonique et le trie shared-prefix lazy opt-in existent, dialogues canoniques. Exécute `scripts.smoke_layer1` et la CI. N'ajoute pas d'anciennes approches : concentrons-nous sur l'analyse grammaticale actuelle, sa correction et sa couverture. »
