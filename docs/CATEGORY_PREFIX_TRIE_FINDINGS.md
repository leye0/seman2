# Reconnaissance par préfixes communs : LE trie lazy retenu

Ce document explique **la seule implémentation de préfixes partagés restant dans `main`**. Pour l'exécution et les règles de routage, voir [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md).

## Pourquoi ce moteur ?

Le parseur canonique construit un état partiel par `(rule_index, dot, start, end)`. Quand plusieurs règles ont un début de RHS catégorie identique, cette reconnaissance peut être répétée. Plutôt que compresser les objets *après* leur création, nous partageons réellement la progression grammaticale des **catégories et spans**.

Un automate compilé regroupe les préfixes RHS de toutes les règles et garde, pour chaque nœud, la liste **distincte des variantes `(rule_index,dot)`**. L'identité complète de chaque règle, son suffixe, ses traits, `requires`, sa valuation et ses relations sémantiques restent accessibles.

## Code actif (aucun concurrent)

- `shared_trie_forest.py` : `compile_category_trie`, `TrieRecognitionBase`. Il n'existe **aucun mode eager** à sélectionner.
- `lazy_trie_forest.py` : `LazySharedTrieForest`, `LazyGroup`, `VirtualPartials`, `LazyRuleDerivations`. Seules les progressions partagées sont créées pendant la reconnaissance; les partials d'une règle donnée deviennent des objets `PackedPartial` uniquement lorsque nécessaires à la matérialisation d'une analyse.
- `vector_chart.py` : `VectorGrammar(...,lazy_trie_recognition=True)` donne ce seul moteur alternatif; son `k-best` est le même que pour le canonique.
- `complexity_routing.py` et `engine.py` : le trie n'est **jamais** le défaut et reste exclu des phrases courtes / dialogues.

Ce trie ne permet **pas** de jeter d'autres variantes lexicales, de partager des traits s'ils divergent, ni de réduire arbitrairement le plafond original de 20 000 états.

## Preuves et mesures

L'ancien audit oracle de 64 phrases non saturées avait montré une possibilité théorique de regrouper **88,3 % des états de préfixes**; ce chiffre ne mesurait PAS de temps économisé. Ensuite, le véritable moteur autonome lazy a économisé **43 % CPU** dans un essai sur 42 phrases longues. Le système complet avec routage a atteint **−15,6 % CPU** dans un audit A/adaptatif/A sur 128 phrases (Action [39177896708](https://github.com/leye0/seman2/actions/runs/39177896708)).

L'équivalence des analyses du canonique et du trie est couverte par `superparser/tests/test_shared_trie_forest.py` sur des cas sans saturation. **Les forêts saturées ne possèdent toujours pas une preuve générale d'équivalence ou de correction.** Ne pas interpréter le gain de vitesse comme un gain de couverture grammaticale.

## Approches explicitement refusées

Les modes expérimentaux `online_prefix_edges`, `flat_prefix_edges`, `indexed_recognition`, `shared_trie_recognition` eager, le cache de frontières, les snapshots de signatures et autres replayers ne sont plus présents dans `main`. L'ancien code reste accessible dans [archive/pre-simplification-2026-10-18](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18) et dans les commits Git.

**Cap actuel :** conserver ces deux moteurs et leur routage, puis travailler sur la justesse des analyses lourdes et des dialogues.
