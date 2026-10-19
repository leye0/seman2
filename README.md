# Seman2 — Layer 1 grammatical anglais

**Ce dépôt a un seul sujet : le parseur grammatical symbolique (Layer 1) actuel.**
Il préserve les mots et leur surface, les alternatives lexicales, les traits morphosyntaxiques, la structure et les dérivations utilisables par un futur Layer 2. Il ne contient aucun ancien parseur concurrent exécutable.

## Commencer ici

1. **[Exécuter le code actuel et connaître TOUS ses points d'entrée](docs/RUN_CURRENT_LAYER1.md)** — référence technique principale, commandes effectivement exécutées dans la CI.
2. [Point de reprise pour une nouvelle conversation/agent](docs/CURRENT_RESEARCH_HANDOFF.md).
3. [Architecture et sorties du Layer 1](docs/ARCHITECTURE_LAYER1.md).
4. [Limites et priorités](docs/KNOWN_LIMITS_AND_ROADMAP.md).
5. [Historique des erreurs et des choix](docs/RESEARCH_HISTORY_AND_DECISIONS.md).
6. [Corpus et intégrité des données](docs/CORPORA_AND_DATA.md).
7. [Manifest du nettoyage et code archivé](docs/CLEANUP_MANIFEST.md).
8. **[Audit CPU Python bas niveau — profilage et tests A/B](docs/LOW_LEVEL_PYTHON_CPU_AUDIT_2026_10_18.md)** — 131 phrases profilées; identification d'un coût majeur des collections GC (sans modifier les algorithmes).
9. **[Benchmark CPU/GC sur 1 000 phrases](docs/GC_CPU_1000_SENTENCES_BENCHMARK_2026_10_18.md)** — test A/B/B/A, 4 000 analyses, mêmes résultats grammaticaux, réduction CPU mesurée de ~40 % sur ce corpus; détail et limites de la mise en production.

## Gestion mémoire en production (CPython)

Le parseur WordNet appelle **une fois par processus** `gc.collect(2)` puis `gc.freeze()` après que les quatre tables POS de WordNet ont été chargées et **avant** la construction d'une forêt d'analyse. Le GC automatique reste activé pour les objets construits ensuite. Aucun changement n'est apporté aux algorithmes grammaticaux, aux budgets ou au caching. Si WordNet n'est pas chargé ou si le GC est déjà désactivé, le gel n'est pas exécuté. **Désactivation immédiate** au démarrage : `SEMAN2_DISABLE_GC_FREEZE=1`.

`gc.freeze()` est **global au processus** et peut prolonger la vie de cycles existants; ne pas l'appeler au hasard dans une application hôte. La réduction d'environ 40 % est mesurée sur 1 000 phrases *avec ressources préchargées*, et ne garantit pas le même gain au premier appel ni sur un million de phrases. Les artefacts historiques des mesures sont disponibles via les liens GitHub Actions des rapports; les scripts de benchmark expérimentaux ont été retirés de `main`.

## Le seul chemin exécuté

`Parser(resources)` est le **parseur canonique**, inchangé pour toutes les entrées par défaut. Lorsqu'une **`ComplexityPolicy` explicitement configurée** est fournie, seules les longues phrases *non citées* dépassant le seuil préparse empruntent **`LazySharedTrieForest`**, qui mutualise la reconnaissance des préfixes et projette les dérivations par règle à la demande. Les petites phrases conservent le chemin canonique **sans calcul de score**, et les dialogues utilisent leur grammaire spécialisée. Les deux moteurs partagent le même `k-best`.

Aucun seuil automatique ou universel n'est activé par défaut. Le test historique de 128 phrases indiquait ~15,6 % de gain CPU adaptatif sur cette cohorte, mais les forêts saturées ne sont pas complètement certifiées; il ne faut pas généraliser la mesure.

### Vérifier que le dépôt fonctionne

Depuis la racine du dépôt, avec Python 3.12+ et `WORDNET_DICT` pointant vers WordNet 3.0 `dict/` :

```bash
WORDNET_DICT=/chemin/wordnet3/dict PYTHONPATH=superparser python -m scripts.smoke_layer1
```

Cette commande teste un texte court, une phrase longue routée vers le trie et un dialogue, y compris l'identité des meilleurs arbres et alternatives avec le canonique.

**Les seules CI pertinentes** sont `core-seman2-validation.yml` (tests et smoke), `dialogue-grammar-regressions.yml`, `clean-novel-corpus-ci.yml`, `direct-grammar-validation.yml` et le benchmark *manuel* `layer1-adaptive-benchmark.yml`.

Les quatre romans nettoyés et l'intégralité de `data/` et `superparser/data/` sont conservés. L'ancien code reste accessible sur [`archive/pre-simplification-2026-10-18`](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18), **pas** dans `main`.

Le travail actuel se concentre sur la **justesse et la couverture grammaticale**, particulièrement les phrases lourdes et les dialogues. La gestion mémoire CPython mesurée est intégrée, sans modifier le fonctionnement linguistique.
