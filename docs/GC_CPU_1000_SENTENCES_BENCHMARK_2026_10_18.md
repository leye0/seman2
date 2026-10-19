# Seman2 — Benchmark CPU/GC sur 1 000 phrases (branche main)

Date : 18 octobre 2026 (heure de Montréal; exécution GitHub Actions le 19 octobre UTC). Python 3.12.15 sur Linux x86-64, GitHub Actions hébergé.

**Exécution réussie :** https://github.com/leye0/seman2/actions/runs/39192349373

**Code benchmark :** [tools/cpu_gc_1000_benchmark.py](../tools/cpu_gc_1000_benchmark.py)  
**Workflow :** [.github/workflows/cpu-gc-1000-benchmark.yml](../.github/workflows/cpu-gc-1000-benchmark.yml)

## Conclusion : amélioration reproductible de 40 % du CPU de parsing

**1 000 phrases distinctes**, issues de quatre romans Gutenberg nettoyés, équilibrées sur quatre catégories de longueur (250 phrases par catégorie, de 4 à 32 tokens). Chacune est analysée quatre fois dans l'ordre **A/B/B/A** : GC automatique normal, ressources gelées par `gc.freeze()`, ressources gelées, puis GC normal. Le GC demeure **activé** dans les deux configurations.

Le chargement WordNet, la compilation du parseur et la constitution des entrées lexicales correspondant aux 1 000 phrases sont terminés avant le chronométrage. Tous les appels analysent **une phrase à la fois**, sans conserver les forêts en mémoire. Les quatre séries utilisent le même processus Python, un seul parseur (cache de résultats désactivé), les mêmes limites et le même code métier. Le chronométrage inclut la construction lexicale, le parsing canonique, l'obtention du meilleur arbre, deux alternatives et la sérialisation/empreinte de sortie.

### CPU réel non instrumenté

| Mesure | GC normal A | Freeze A | Freeze B | GC normal B |
|---|---:|---:|---:|---:|
| CPU total (s) | 120,758 | 70,249 | 71,782 | 116,015 |
| CPU des collections GC (s) | 64,564 | 15,330 | 15,944 | 60,422 |
| CPU hors GC estimé (s) | 56,194 | 54,919 | 55,839 | 55,593 |
| CPU collection complète post-série (s) | 0,443 | 0,428 | 0,416 | 0,402 |
| Latence P50 (ms) | 36,32 | 33,96 | 34,83 | 36,21 |
| Latence P95 (ms) | 527,53 | 91,44 | 92,70 | 490,73 |
| Latence P99 (ms) | 1 946,82 | 1 852,77 | 1 895,85 | 1 891,65 |
| Grammaires complètes | 533 | 533 | 533 | 533 |
| RSS au début (MiB) | 279,23 | 359,69 | 370,40 | 379,36 |
| RSS à la fin (MiB) | 359,69 | 370,40 | 379,36 | 385,50 |

Moyennes des deux séries : **118,38664 s** en régime normal contre **71,01560 s** avec `gc.freeze()`, soit **−40,014 %** de CPU. Nettoyage explicite final, identique en intention, inclus : **118,80953 s** contre **71,43773 s**, soit **−39,872 %**.

Sur ces 1 000 phrases, le GC normal utilise en moyenne **62,493 s** (52,8 % du CPU total); le gel utilise **15,637 s** (22,0 %). Le CPU hors GC est quasiment identique entre les régimes : environ **55,9 s vs 55,4 s**, ce qui lie clairement le gain au collecteur, pas à un changement du parcours grammatical.

## Contrôle d'identité des analyses

**Toutes les 1 000 empreintes de chaque série concordent avec celles des autres séries.**

Le calcul inclut : résultat `completed`, meilleur arbre sérialisé, deux alternatives sérialisées, tous les compteurs non temporels de `ParseResult.stats`. Seules les mesures de durée, intrinsèquement variables, sont exclues des empreintes.

Les 533 phrases complètement reconnues et les 467 autres conservent leur statut. Le benchmark ne prétend pas mesurer l'exactitude linguistique : 533/1000 est le nombre de `completed` pour **ce** corpus et ces limites.

### Résultat par longueur

| Nombre de tokens | Phrases | Ratio CPU freeze / GC normal | Réduction CPU |
|---|---:|---:|---:|
| 4–8 | 250 | 0,5781 | 42,2 % |
| 9–16 | 250 | 0,3943 | 60,6 % |
| 17–24 | 250 | 0,6843 | 31,6 % |
| 25–32 | 250 | 0,5606 | 43,9 % |

L'intervalle bootstrap exploratoire sur les 1 000 ratios appariés donne 0,52594–0,64441 pour le ratio CPU freeze / normal, soit une réduction de l'ordre de 35,6 à 47,4 %. Il ne remplace pas des runs sur **machines ou processus indépendants** et n'explique pas les dépendances temporelles dues au GC.

## Les événements du GC

| Compteur par série | GC normal | Freeze |
|---|---:|---:|
| Génération 0 | 101 192 collections | 101 656 |
| Génération 1 | 9 199 collections | 9 241 |
| Génération 2 | **125 collections** | **814 collections** |

Les collections majeures sont *plus nombreuses*, mais nettement moins coûteuses après gel. Le coût CPU total des collections de génération 2 passe d'environ **56,7 s** à **10,0 s** par série. Les objets gelés au début des bras B sont environ **1 532 100**, contre ~375 objets déjà gelés lors des bras A sans optimisation.

Les données montrent une réduction du coût de parcours des objets du GC, non une réduction du nombre d'analyses ou des dérivations.

## Mémoire — ce que la campagne prouve (et ne prouve pas)

Tous les bras utilisent **le même processus**, successivement. Le RSS passe globalement d'environ **279 MiB au début** à **386 MiB à la fin**; le pic `ru_maxrss` du processus est d'environ **393 MiB**. Par séquence : normal A, +80 MiB; freeze A, +11 MiB; freeze B, +9 MiB; normal B, +6 MiB.

L'augmentation du premier bras peut provenir d'initialisations résiduelles, d'allocateurs, de caches lexicaux ou d'objets Python durables; les relevés RSS ne distinguent pas ces causes. **Il serait incorrect de comparer directement 279 MiB du bras normal A à 360 MiB du bras freeze A comme un surcoût dû à `gc.freeze()`** : les bras sont séquentiels.

Les valeurs RSS sont échantillonnées tous les 100 cas, pas à la fréquence des allocations. Cette campagne **ne démontre ni une fuite mémoire, ni l'absence de fuite à 1 million de phrases**. Il faut des processus frais et un test de plusieurs dizaines ou centaines de milliers de phrases pour établir la pente de mémoire stabilisée.

Le P95 tombe d'environ 500 à environ 92 ms, mais **le P99 demeure voisin de 1,9 s**. Les phrases exceptionnellement lentes ne sont donc pas toutes ralenties par le GC. On n'a pas modifié l'algorithme d'analyse.

## Correction méthodologique

La première tentative [run #39191960706](https://github.com/leye0/seman2/actions/runs/39191960706) avait mesuré le bras normal complet puis échoué sur la parité de la deuxième phrase lors du premier bras freeze. La cause hypothétique était la construction paresseuse des entrées lexicales au cours du premier bras. Le nouveau protocole **préchauffe toutes les 1 000 surfaces** avant les mesures, et vérifie des phrases répétées. Le nouveau run est **vert avec 4 000/4 000 empreintes identiques**.

L'exécution complète est disponible avec six fichiers JSON : métadonnées et ensemble fixe d'entrées, quatre séries comprenant chacune 1 000 temps CPU et signatures, et synthèse.

## Conséquences techniques

**Oui, l'optimisation runtime semble très prometteuse :** une réduction d'environ 40 % de CPU est reproductible sur ce corpus équilibré, sans modification sémantique. En revanche, **ne pas ajouter `gc.freeze()` dans `Parser.__init__` sans étude supplémentaire** : c'est une politique globale du processus Python, pas un gel sélectif de WordNet. Le moment précis du gel, sa durée et les ressources prises au piège peuvent provoquer de la rétention de cycles.

Au-delà de 1 000 phrases et à 1 million, le gain n'est **pas démontré**; seul le principe général de diminution du travail du GC est compatible avec une montée en charge. Un audit de RSS avec processus indépendants, workload continu et collecte des objets temporaires est le prochain garde-fou.

**Aucun fichier du moteur de production n'a été modifié.**
