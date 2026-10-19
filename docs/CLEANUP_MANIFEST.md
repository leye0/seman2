# Manifest du nettoyage de Seman2 sur `main`

**Référence conservée AVANT ce nettoyage** : commit `d161e4bc34f2c344a7360d92329f2dd985133acd` sur la branche [`archive/pre-simplification-2026-10-18`](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18). L'ancien code et les anciennes CI sont récupérables depuis cette branche et l'historique Git, **pas présents dans la branche `main` simplifiée**.

## Le principe

`main` contient uniquement **le Layer 1 grammatical actuel**, ses ressources linguistiques, ses tests et des outils d'évaluation de CE moteur. Nous n'entretenons plus de copies exécutables de paradigmes GLR, reading kernel, système cognitif initial, induction, C/hybride, snapping, stockage de préfixes alternatif ou analyse de discours/coréférence héritée.

### Opérations réalisées

- Supprimés : le répertoire `archives/` historique, les nombreux prototypes d'induction, les expériences GLR et anciennes analyses, les patches/rapports historiques, anciens fichiers racine et exigences non utilisées.
- Supprimés : `seman_parser/prefix_edges.py` et les paramètres `online_prefix_edges` / `flat_prefix_edges`, `shared_trie_recognition` eager, `cache_boundaries` et `early_lexical_filter`, après leurs expériences sans gain suffisamment établi.
- Supprimés : les scripts et tests propres aux méthodes abandonnées, les anciennes Actions de benchmarking à chaque push, les anciens modules de discours / coréférence non intégrés au Layer 1.
- Conservés : `Parser`, `VectorGrammar`, `_VectorForest` et `LazySharedTrieForest`, prévision des débuts de règles, grammaire des dialogues, `k-best`, sorties syntaxiques/sémantiques.
- Construit : `superparser/scripts/smoke_layer1.py`, la CI canonique + trie lazy + dialogue et une documentation de reprise technique [`RUN_CURRENT_LAYER1.md`](RUN_CURRENT_LAYER1.md).
- Corrigé : `pyproject.toml` pointe vers `superparser` au lieu d'un ancien répertoire inexistant `src`.

### Données préservées

**Aucune suppression intentionnelle** de `data/`, `superparser/data/` ni `superparser/research/verbnet_lr/corpora/`. Les fichiers Gutenberg nettoyés (David Copperfield, Pride and Prejudice, Frankenstein, Treasure Island), le manifeste, WordNet non versionné, les lexiques et grammaires restent à leur place. Pour les SHA historiques des romans, utiliser les manifests et l'ancienne branche sauvegardée.

**Wikipédia :** aucun fichier dont le nom contenait wiki / Wikipédia / Wikidata n'a été repéré dans l'arbre Git précédent. Cette absence **n'est pas** une preuve de suppression ou d'inexistence ailleurs.

### Vérifier

Exécuter `WORDNET_DICT=/chemin/wordnet3/dict PYTHONPATH=superparser python -m scripts.smoke_layer1`. Lancer aussi la CI `.github/workflows/core-seman2-validation.yml`. Les autres workflows présents ne concernent que les romans nettoyés, la grammaire, les dialogues et le **benchmark manuel** du routeur courant.

**Règle de ménage future :** retirer de `main` toute expérience abandonnée et consigner les enseignements en prose dans [`RESEARCH_HISTORY_AND_DECISIONS.md`](RESEARCH_HISTORY_AND_DECISIONS.md). L'historique Git suffit à récupérer l'ancien code; pas besoin de laisser un deuxième moteur dans le dépôt.
