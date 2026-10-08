# Seman2 Parser — Historique des performances

Métriques mesurées sur `data/the_map_of_everything_nlp_novel.txt`
(lexique WordNet 3.0 vivant, grammaire déclarative).

## Protocole

```python
# vitesse : 40 phrases du roman, WordNet pré-chargé
from seman_parser.engine import Parser
from seman_parser.coverage import extract_sentences
# parse une par une, mesurer time.perf_counter

# couverture : run_coverage(limit=N) sur le roman
```

---

## Journal

### 2026-10-08 — avant optimisation perfs

**Vitesse (40 phrases, WordNet chaud)**

| Métrique | Valeur |
|---|---|
| médiane | **332 ms** |
| moyenne | 2 682 ms |
| p90 | 9 813 ms |
| min | 10 ms |
| max | 37 891 ms |

**Couverture roman**

| Échantillon | Parsées | Taux |
|---|---|---|
| 20 premières | 15 | 75 % |
| 30 premières | 25 | 83.3 % |
| 50 premières | 37 | 74 % |
| 200 premières | 95 | 47.5 % |

**Tests** : 50+ tests unitaires/intégration OK

**État des optimisations présentes**

- interned symbols, packed forest, type bitsets
- WordNet singleton, cache lemma → entrées
- beam par nœud (80) + budget max_items (50 000)
- pas de suffix-stripping sur mots-outils

**Manquants identifiés**

- cache de phrase / lattice
- hash-consing des feature structures
- cache d'unification
- index de règles riche (cat, vform, wh, gap)
- filtrage contextuel de POS
- exclusion de non-sens (lectures WordNet absurdes)
- Earley / left-corner filtering
- bounded beam global

---

<!-- nouvelles entrées ci-dessous -->

### 2026-10-08 — index dans chart.py (en cours)

**Changements**

- index `_packed_by_start[(start, cat)]` — fin du balayage du forest
- index `_partial_by_wait[(pos, cat)]` — fin du balayage des partiels
- `_offer_partial` garde 3 variantes par slot (traits/bindings distincts)
- `_advance_partial_from_chart` en worklist (plus de récursion)
- budget adaptatif selon longueur (16/28/48 beam)
- parse cache + lattice cache LRU

**Vitesse (15 phrases, WordNet chaud)**

| Métrique | Avant | Après |
|---|---|---|
| médiane | 332 ms | 515 ms |
| moyenne | 2 682 ms | 2 278 ms |
| max | 37 891 ms | 16 008 ms |
| p90 | 9 813 ms | ~3 500 ms |

**Lecture honnête**

- le max est divisé par 2,4 (le budget adaptatif borne les longues)
- la médiane a *monté* : les 3 variantes par slot coûtent sur les phrases
  courtes, là où le balayage était déjà bon
- le hash-consing des FS a été retiré (clé `tuple(sorted(items))` trop
  chère — insight de l'utilisateur : interner en parallèle, pas dans le
  chemin chaud)
- `intern_fs` / `unify_cached` sont définis dans `perf.py` mais non
  branchés (volontaire après mesure négative)

**Prochaine étape** : ne garder plusieurs variantes que quand les traits
diffèrent réellement, et réduire le budget des phrases moyennes.

### 2026-10-08 — profilage cProfile + graphe sémantique

**cProfile sur "John opened the box." (0.67 s)**

| Fonction | % du temps | Appels |
|---|---|---|
| `apply_action` (semantics) | **67 %** | 504 |
| `_compose_semantics` | 68 % cumul | 504 |
| `unify` | 9 % | 6 744 |
| `_offer_partial` | 6 % | 4 713 |
| `_advance_partial_from_chart` | 5 % | 838 |

**Diagnostic** : `apply_action` re-mergeait tous les graphes enfants à
*chaque* action sémantique. N actions = N copies.

**Correctifs**

- `SemanticGraph.merge_all()` — une passe, zéro copie intermédiaire
- `_compose_semantics` pré-merge les enfants **une fois**, puis applique
  les actions sur le graphe déjà fusionné
- `_complete` : rejet rapide si le slot est plein et le score insuffisant
  (avant de composer la sémantique)
- `_same_analysis` compare maintenant l'identité des enfants

**Vitesse (15 phrases) — série complète**

| Métrique | Origine | +index | +merge_all |
|---|---|---|---|
| médiane | 332 ms | 515 ms | 569 ms |
| moyenne | 2 682 ms | 2 278 ms | **1 058 ms** |
| max | 37 891 ms | 16 008 ms | **5 897 ms** |
| tests | OK | OK | 22 OK |

Le max est divisé par 6.4 depuis le départ. La médiane reste haute sur
les phrases moyennes — à creuser via le coût fixe de `dict(handles)` par
action.

**Non fait (volontairement)** : fusion des variantes par traits —
dangereux pour l'ambiguïté structurelle (insight de l'agent utilisateur).

### 2026-10-08 — signatures + set de dédup + correctifs anomalies

**Anomalies corrigées (diagnostic de l'agent utilisateur)**

1. `_packed_by_start` écrasait les constituants même position/catégorie,
   fins différentes → stocke une **liste** de nœuds
2. `_same_chart_item` ignorait les sous-arbres → signature structurelle
   complète (règle + handles + enfants)
3. `_complete` rejetait avant unification → rejet **sûr** seulement :
   slot plein **et** ≥4 règles distinctes **et** score < best − 2.0

**Déduplication par signature (set O(1))**

Avant : `any(_same_analysis(...) for a in alternatives)` = O(n) avec
comparaison profonde → 6.4M d'appels, 44 % du CPU.

Après : `item.signature() in node.seen_signatures` = O(1).

**cProfile phrase longue (73 mots)**

| | Avant | Après |
|---|---|---|
| appels de fonctions | 32.8 M | **7.3 M** |
| temps total | 17.2 s | **7.9 s** |
| `_offer` | 9.1 s | 1.0 s |
| `_same_analysis` | 6.4M appels | **absent** |

**Vitesse (15 phrases) — état final**

| Métrique | Origine | Actuel | Variation |
|---|---|---|---|
| médiane | 332 ms | 681 ms | +105 % |
| moyenne | 2 682 ms | **2 522 ms** | −6 % |
| max | 37 891 ms | **12 074 ms** | **−68 %** |
| p90 | 9 813 ms | ~5 000 ms | −49 % |

**Couverture (non régressée)**

| Échantillon | Avant | Après |
|---|---|---|
| 15 phrases ambiguës | 15/15 | **15/15** |
| 30 phrases roman | 80 % | **80 %** |
| tests | 43 OK | **43 OK** |

**Ambiguïté** : alternatives conservées (8 à 702 sur les 15 phrases).
Léger tassement vs avant (le cap de 2 variantes par slot), mais
`I saw the man with the telescope` garde encore 336 analyses.

**Restant connu** : la médiane a monté (coût fixe des signatures et des
index sur les phrases courtes). Prochaine étape selon l'agent :
structures persistantes partagées, si le profilage le justifie.
