# Analyse de performances Seman2 V3

État au 2026-10-07 après profiling sur le roman
`data/the_map_of_everything_nlp_novel.txt` (1000 phrases) et la suite
d'intégration TRIPS locale.

---

## 1. Méthodologie

Chaque hypothèse a été isolée par chronométrage de sous-fonctions, avec
compteurs d'appels (`wrap` sur les méthodes du store) et mesures SQL brut
vs conversion Python. Les chiffres ci-dessous viennent de runs réels, pas
d'estimations.

Outils :
- `time.perf_counter()` autour de chaque étape de `process_next` ;
- compteur de calls monkeypatché sur `LearningStore` et `CoupledLearningRuntime` ;
- `SELECT COUNT(*)` et lecture brute de `learned_structures` pour isoler le SQL
  de la désérialisation ;
- comparaison `outbox_enabled = True/False` sur les mêmes écritures.

---

## 2. Profil final (15 phrases, roman réel)

| Étape | ms/phrase | Part |
|---|---|---|
| `claim_next` (SQLite) | 32 | 3 % |
| **TRIPS (KQML/TCP loopback)** | **908** | **87 %** |
| `persist_analysis` (SQLite) | 6 | <1 % |
| `observe` (mémoire) | 31 | 3 % |
| **Total** | **~980** | 100 % |

TRIPS est le seul goulot significatif. C'est le chart parser lui-même, pas
le transport (KQML sur socket locale, pas d'HTTP) ni la persistance.

---

## 3. Ce qui a été découvert

### 3.1 TRIPS : compilation et protocole

- **Bytecode Java 26 vs JRE 17.** Les jars `etc/java/TRIPS.*.jar` avaient
  été construits avec Homebrew OpenJDK 26 (`major version: 70`) alors que
  `activate_local.sh` force un Temurin 17 (`major: 61`). Le Facilitator
  refusait de démarrer (`UnsupportedClassVersionError`).
  **Correction :** recompilation de tous les paquets Java avec
  `javac --release 17` (`KQML`, `util`, `TripsModule`, `Facilitator`,
  `KeyboardManager`, `SpeechOutNot`, `CollaborativeStateManager`, `AKRL`),
  puis `make install` pour propager les jars.

- **`_matches_uttnum` ne trouvait pas les réponses.** Le `:UTTNUM` est
  imbriqué dans les `UTT` de `:ACTS` d'un `COMPOUND-COMMUNICATION-ACT`,
  pas en tête du message. Le client attendait jusqu'au timeout alors que
  la réponse était déjà arrivée (~15 s).
  **Correction :** `_contains_uttnum` parcourt l'arbre récursivement.

- **Les paragraphes multi-phrases explosent.** TRIPS les envoie en
  `COMPOUND-COMMUNICATION-ACT` et le coût devient combinatoire. Une phrase
  : 0,5 s. Trois phrases : timeout à 150 s.
  **Correction :** mode `sentence` à l'ingestion + segmentation candidate
  dans `_compose_input` (une seule phrase envoyée au chart parser).

- **Le contexte était concaténé dans l'entrée.** `_compose_input` collait
  les unités de contexte + la phrase courante, ce qui recréait du
  multi-phrases à chaque appel.
  **Correction :** seule la phrase cible part au parser ; le contexte reste
  de la provenance (`context_evidence_ids`).

- **`number_parses_desired=10` par défaut.** Le CLI utilisait la valeur
  par défaut du constructeur, qui demandait 10 analyses par phrase.
  **Correction :** défaut à 1, option `--parses-desired` au CLI.

### 3.2 disco-dop

- **Arbres non binarisés.** `recurringfragments` refusait les productions
  ternaires (`ValueError: non-binarized production`).
  **Correction :** `binarize()` à l'entrée, `unbinarize()` à la sortie pour
  retrouver les libellés natifs.

- **Feuilles sans index.** Les nœuds sans token (`(W::PUNC ))`) devenaient
  des frontières vides que `getctrees` refusait.
  **Correction :** `discodop_tree` supprime les feuilles non ancrées plutôt
  que d'émettre `(label )`.

- **`maxdepth > 0` renvoie tous les fragments « cover »**, même ceux vus une
  fois. 89 arbres → 69 859 fragments.
  **Correction :** filtre `min_fragment_nodes`, `max_fragments_per_run`,
  `maxdepth=3`.

### 3.3 LearningStore — écritures

- **Une transaction SQLite par `put_structure`/`put_relation`.** Chaque
  objet déclenchait `BEGIN IMMEDIATE` + commit + un INSERT dans
  `graph_sync_outbox`. 2000 structures = 4,4 s.
  **Correction :** batch `with self.store.batch()` sur tout un run de
  consolidation ; un seul flush à la fin.

- **`graph_sync_outbox` doublait chaque écriture.** L'outbox n'est utile
  que si AtomSpace est présent.
  **Correction :** `outbox_enabled = False` par défaut ; le payload
  `canonical_json(structure.as_dict())` n'est calculé que si l'outbox est
  active.

- **`canonical_json` recalculé pour l'outbox même désactivé.**
  **Correction :** condition sur `outbox_enabled` avant sérialisation.

- **`structures()` appelait `flush()` même pendant un batch**, ce qui
  commitait au milieu et forçait un aller-retour disque.
  **Correction :** `flush()` est un no-op pendant un batch ; `structures()`
  fusionne mémoire + disque.

### 3.4 LearningStore — « conscience » en mémoire

- **`_remember_support` faisait un scan linéaire** sur chaque liste de
  supports pour la déduplication. Avec 50 000 supports, c'est O(n²).
  **Correction :** `_support_keys` (set de tuples) pour une recherche O(1).

- **`_by_evidence` était une liste** avec `if structure_id not in linked`
  linéaire.
  **Correction :** passé en `set`, `discard()` à l'éviction.

- **`_evict_if_needed` faisait `tuple(self._structures.items())` à chaque
  objet évincé** — O(n²) sur le working set complet. C'est la cause des
  pics de 2–5 s dans `observe`.
  **Correction :** éviction en masse (calcul de l'excédent une fois,
  parcours LRU unique).

- **Capacité à 50 000 alors que le working set réel montait à 146 849
  objets** (structures + relations + contexts), ce qui forçait l'éviction
  en boucle.
  **Correction :** capacité par défaut à 250 000.

- **`flush_interval = 2.0 s` interrompait la boucle chaude.** Le timer se
  déclenchait pendant que TRIPS travaillait et forçait un flush disque.
  **Correction :** intervalle à 15 s ; le flush par volume est passé à
  20 000 pending (contre 2 000). Le flush temporel n'est qu'une sécurité
  au repos.

- **`load_family('dop-fragment')` scannait 36 000 lignes** au premier
  appel, à chaque réouverture du store.
  **Correction :** `_families_loaded` évite les rechargements ; le scan
  reste pour le premier appel mais ne se répète pas.

### 3.5 `observe` — explosion de structures

- **~180 structures par phrase** (nœuds de projection, fragments
  structurels, alignements, contextes) = ~920 écritures par phrase.
  Sur 238 phrases : 43 603 structures + 90 616 relations + 50 408 supports.
  **Correction :** `observe` ne stocke plus que l'essentiel (~8 structures
  par phrase) : `evidence-reference`, `analysis-reference`,
  `hypothesis-reference`, `semantic-observation`, `structural-observation`,
  `treebank-observation`, `alignment`, `context-sequence`. L'expansion
  nœuds/fragments est déléguée à la consolidation, depuis le payload de
  projection déjà complet.

- **`structural_fragments` énumérait chaque sous-arbre à chaque
  profondeur** (O(n × depth) par arbre).
  **Correction :** `max_depth=3`, `max_fragments=32`, filtre
  `min_fragment_nodes`.

### 3.6 Boucle rétro

- **All-pairs fragments × arbres.** 2000 fragments × 48 arbres = 96 000
  tentatives de matching, chaque tentative reparsait l'arbre hôte.
  **Correction :**
  - index par étiquette racine (`_fragment_root_label` / `_tree_labels`) ;
  - parsing de l'arbre hôte une seule fois par arbre
    (`match_fragments_on_tree`) ;
  - plafond `max_matches_per_tree` (64) ;
  - échantillonnage des candidats, tri par longueur décroissante.

### 3.7 Induction — croissance guidée

- **Anti-unification de tous les groupes** = 2035 patterns + 7535 bindings
  par run, même pour des empreintes uniques.
  **Correction :** `GrowthInducer` (`learning/growth.py`) :
  - `RecurrenceIndex` (hash → count, first_seen, last_seen, supports) ;
  - sélection par récurrence (`minimum_support`) ;
  - croissance locale par co-observation uniquement ;
  - scoring compression / non-redondance / prédiction / stabilité
    d'alignement (la fréquence brute ne pèse que 5 %) ;
  - un peu d'exploration (`rng`) mais jamais comme moteur principal ;
  - empreintes de forme cachées (`_shape_cache`) pour éviter la
    resérialisation JSON à chaque scoring.

### 3.8 Streaming d'ingestion

- **Mode `sentence`** ajouté à `text_blocks` : découpe candidate après
  `.!?` quand la suite commence par une majuscule ou une ponctuation de
  fermeture. Les offsets byte exacts sont conservés dans `source`.

---

## 4. Ordre de grandeur des gains

| Problème | Avant | Après |
|---|---|---|
| Ingest 3 phrases multi-phrase | timeout 150 s | 0,5 s/phrase |
| `observe` | 1336 ms/phrase | 31 ms/phrase |
| Consolidation 90 phrases | 39 s | 3 s |
| Écriture 2000 structures | 4,4 s | 0,1 s (batch) |
| Éviction working set | O(n²) | O(n) |
| `structures(alignment)` 36k lignes | 37 s | 0,27 s (cache) |
| Boucle rétro 2000×48 | all-pairs | indexé + 1 parse/arbre |

---

## 5. Ce qui reste

- **TRIPS ≈ 900 ms/phrase** : c'est le coût réel du chart parser sur des
  phrases de roman (0,4 s pour une phrase courte, 3–8 s pour une phrase
  complexe). Le profil `params.lisp` (beam pruning, un seul parse,
  stop-when-solutions-found, Graphviz off, tracing off) est déjà actif.
  Aucune micro-optimisation locale ne divisera ce chiffre par 10.

- **Parallélisme nécessaire pour 12M de phrases.** Plusieurs instances
  TRIPS indépendantes (une par document/conversation), chacune gardant son
  propre contexte. Le plan d'optimisation (`optimisation_ideas.md` §32)
  décrit le modèle : worker 1 → documents A, worker 2 → documents B, etc.
  Ne jamais paralléliser les phrases d'une même conversation.

- **Cache d'analyses** (`optimisation_ideas.md` §33) : hash de
  `raw_text + parser build + profile + context id`. Un corpus répète
  beaucoup ; TRIPS ne devrait jamais reparser gratuitement.

- **Segmentation par abréviations.** `Mr.` est découpé en deux phrases
  (`A librarian named Mr.` / `Chen showed them…`), ce qui crée des
  fragments pathologiques pour le parser. Un dictionnaire d'abréviations
  améliorerait la qualité des frontières.

- **AtomSpace / Miner** non installés : `opencog` absent du venv. Les
  adapters retournent `available: false` explicitement, sans fallback.

---

## 6. Fichiers touchés par les optimisations

| Fichier | Changements |
|---|---|
| `src/seman2/learning/store.py` | mémoire-first, batch, outbox, éviction, flush timer, `_support_keys`, `_by_evidence` en set |
| `src/seman2/learning/engine.py` | observe allégé, croissance guidée, index racine, bornes fragments/matches, échantillonnage |
| `src/seman2/learning/growth.py` | `RecurrenceIndex`, `GrowthInducer`, scoring compression/novelty/prédiction |
| `src/seman2/learning/fragments.py` | parse/match/instantiate/linearize des fragments DOP |
| `src/seman2/learning/retro.py` | matching multi-fragments sur un arbre hôte unique |
| `src/seman2/learning/structures.py` | `discodop_tree` sans feuilles vides, `structural_fragments` borné |
| `src/seman2/adapters/discodop.py` | binarize/unbinarize, probe fonctionnel |
| `src/seman2/interpretation/kqml.py` | `_contains_uttnum` récursif |
| `src/seman2/interpretation/trips_adapter.py` | `_compose_input` phrase seule, `number_parses_desired=1` |
| `src/seman2/evidence/stream.py` | mode `sentence` avec offsets byte |
| `src/seman2/__main__.py` | `--parses-desired`, mode `sentence`, CLI `retro` |
| `scripts/seman2` | `test-trips` via `discover` (conflit `tests.py` disco-dop) |
| `.local/src/cogent-v3/src/Systems/cogent/params.lisp` | profil rapide TRIPS |
| `.local/src/cogent-v3/etc/java/*.jar` | recompilation `--release 17` |

---

## 7. Vague d'optimisation du chart TRIPS — 2026-10-07

Un profil statistique SBCL sur une phrase complexe a montré que le coût
restant était dominé par les listes d'association, la substitution et les
recherches répétées dans le chart, et non par KQML/TCP.

Modifications appliquées dans `patches/cogent/seman2-runtime.patch` :

- le contrôle `check-for-common-vars`, décrit par TRIPS comme une vérification
  de débogage, est désactivé par défaut mais reste activable ;
- les constituants ont un index par nom et un cache exact par
  `(position, catégorie)`, mis à jour sans changer leur ordre historique ;
- les messages de pruning ne sont plus imprimés hors mode trace ;
- les loggers Lisp et le journal exhaustif du Facilitator sont effectivement
  désactivables ;
- `number-interps-desired` possède maintenant un handler borné, qui règle à
  la fois le nombre d'analyses recherchées et retournées ;
- le client Seman2 n'envoie plus d'expression Lisp arbitraire avec `eval` ;
- le build Java force du bytecode Java 17 même avec un compilateur hôte plus
  récent ;
- `trips-start` attend désormais une réponse réelle du Parser, et non la
  simple ouverture du port du Facilitator.

La projection structurelle rattache aussi aux offsets source les ponctuations
présentes uniquement dans l'arbre TRIPS. Par exemple, les trois virgules et le
point final de la phrase de contrôle sont tous conservés avec leurs spans ; le
payload KQML natif demeure inchangé.

Sur les 15 premières phrases du même roman, le temps TRIPS observé est passé
de **908 ms/phrase** dans le profil précédent à **609 ms/phrase** (médiane
330 ms), soit environ **33 % de moins** sur cet échantillon. Sur les trois
phrases complexes utilisées pendant l'audit, la moyenne est passée d'environ
1,90 s à 1,35 s.

Validation : 35 tests unitaires, le test d'intégration TRIPS local avec deux
hypothèses, la sonde de santé Parser et l'application inverse du patch Cogent
réussissent.

---

## 8. Mode paragraphe vs mode phrase — 2026-10-07

Avec les optimisations du chart (beam pruning, 1 parse, strict semantics,
patch `Chart.lisp` de GPT), le mode paragraphe ne casse plus. Avant ces
changements, un paragraphe de 3 phrases dépassait 150 s de timeout ;
maintenant le pire observé est 3,3 s.

### Comparaison contrôlée (12 paragraphes du roman, 66 phrases)

| Mode | Total | Par unité | Équivalent / phrase |
|---|---|---|---|
| **Paragraphe** | **25,6 s** | 2133 ms | **~388 ms** |
| Phrase | 51,3 s | 777 ms | 777 ms |
| Ratio | **paragraphe 2× plus rapide** | | |

### Cohérence (260 paragraphes supplémentaires, run interrompu)

Moyenne stable à ~2100 ms/paragraphe, médiane cohérente, **0 échec**,
aucun dérapage RAM. L'échantillon est suffisant pour conclure.

### Pourquoi le paragraphe est plus rapide

Le coût fixe par requête KQML est dominant : chaque `parse()` fait
`register` + 3 `subscribe` + config parser + usurpation TextTagger
(4 messages) + attente de réponse. En mode phrase ce coût est payé 66 fois ;
en mode paragraphe, 12 fois. Le chart parser lui-même est plus efficace
par mot (388 ms pour ~13 mots équivalents vs 777 ms).

### Recommandation

**Revenir au mode paragraphe** pour l'ingestion du roman et des corpus
similaires. Le mode `sentence` reste utile pour les dialogues et les
entrées très longues, mais il n'est plus le défaut nécessaire.

Le mode paragraphe produit aussi un `COMPOUND-COMMUNICATION-ACT` unique
par paragraphe, ce qui préserve mieux les relations inter-phrases
(ponctuation, coordination, subordination) que des analyses isolées.

### Impact pour 12M de phrases

| Hypothèse | Débit | Durée estimée (1 worker) |
|---|---|---|
| phrase (777 ms) | 1,3 phrase/s | ~9 200 h |
| paragraphe (388 ms équiv.) | 2,6 phrase/s | ~4 600 h |
| paragraphe, 8 workers | ~20 phrase/s | **~580 h** |
| paragraphe, 16 workers | ~40 phrase/s | **~290 h** |

Le parallélisme reste indispensable, mais le mode paragraphe divise déjà
par 2 le travail par unité.
