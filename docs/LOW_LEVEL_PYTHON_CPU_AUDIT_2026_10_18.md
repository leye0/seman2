# Seman2 / main — audit des coûts CPU **Python bas niveau**

_Date des runs : 18 octobre 2026 (Montréal), 19 octobre UTC. Toutes les mesures sur GitHub Actions Ubuntu, Python 3.12.15, x86-64, 2 CPU visibles._

## Résultat principal

**Un coût majeur de CPython, pas un défaut de stratégie grammaticale, a été mesuré.**
Le garbage collector scanne un très grand graphe d'objets Python durables (WordNet, grammaire et autres ressources chargées). Lorsqu'on fige ces objets avec **\`gc.freeze()\` après le préchargement**, tout en **laissant le GC automatique activé**, le même parsing prend ~**41,9 % moins de CPU** dans l'expérience A/B/B/A sur 67 phrases, ou ~**39,3 % moins de CPU** en incluant la collection complète réalisée après chaque passage.

Il s'agit d'une **expérience**, pas d'un correctif déployé. Le moteur, la grammaire, les limites, le routage, les caches et le corpus **n'ont subi aucune modification**. \`gc.freeze()\` modifie le comportement du GC du processus; cela requiert des tests de mémoire et de durée de vie avant toute recommandation de production.

### Preuves brutes

- [Profil détaillé 19 phrases, par fonction/ligne/mémoire](https://github.com/leye0/seman2/actions/runs/39188678707)
- [Profil étendu 131 phrases](https://github.com/leye0/seman2/actions/runs/39190114935) : le cProfile a terminé et son artefact est disponible, puis un problème d'indentation dans la phase A/B a entraîné l'échec du premier workflow; le parseur n'a pas échoué
- [A/B Python corrigé, trois variantes, 67 phrases, succès](https://github.com/leye0/seman2/actions/runs/39190367913)
- [Isolement du temps GC et du nettoyage, 67 phrases, succès](https://github.com/leye0/seman2/actions/runs/39190770294)
- [GC freeze A/B/B/A, 67 phrases, succès](https://github.com/leye0/seman2/actions/runs/39191007301)

Les fichiers \`.pstats\`, JSON par fonction/ligne, relevés de mémoire, signatures exactes des sorties et fichiers de résultats par phrase sont joints aux runs.

## 1. Périmètre : ce que cet audit mesure, et ce qu'il n'optimise pas

Objectif : les coûts du langage, du runtime, des allocations, des appels Python, des boucles, des copies de conteneurs, de la gestion des objets, de l'unification et des conversions.

**Exclus** : nouvelles règles linguistiques, changement de forêt/algorithme de recherche, nouveaux chemins heuristiques, modification du beam, changements de stratégies de cache ou du nombre de dérivations.

Il faut distinguer :
1. CPU réel sans instrumentation (\`time.process_time_ns\`).
2. Temps propre et inclusif **instrumentés** avec \`cProfile\`, qui peuvent être considérablement ralentis par le profilage.
3. Temps de lignes via \`line_profiler\`, sous instrumentation encore plus intrusive; lignes appelantes et fonctions appelées ont des temps imbriqués.
4. \`tracemalloc\` : allocations **encore vivantes** à la fin des fenêtres, pas le nombre d'allocations temporaires.
5. Les micro-variantes A/B qui conservent strictement les arbres, alternatives, contraintes et compteurs, testées uniquement par remplacement temporaire de méthodes **en mémoire**.

## 2. Profilage étendu — 131 phrases (128 romans + 3 témoins)

| Mesure | Valeur |
|---|---:|
| Phrases auditées | 131 |
| Parses complets | 65 |
| États partiels construits | 1 237 542 |
| Nœuds de forêt | 42 774 |
| CPU avec cProfile | 117,66 s |
| Appels \`_add_partial\` | 1 357 573 |
| Appels \`_next_start\` | 1 060 884 |
| Appels \`_deref\` | 967 217 |
| Appels \`FeatureStructure.items\` | 599 904 |
| Appels \`_advance\` | 464 421 |
| Appels \`unify_values\` | 407 683 |
| Appels \`_variable_names\` | 328 824 |

**Attention** : le nombre de phrases complétées est une mesure de couverture des entrées sélectionnées, pas une régression démontrée.

### Temps CPU propre par fonction, sous cProfile

Les durées ci-dessous sont des **temps instrumentés** et ne doivent pas être interprétées comme des économies directes possibles.

| Emplacement | Appels | CPU propre instrumenté | CPU cumulatif instrumenté |
|---|---:|---:|---:|
| [\`vector_chart.py:_add_partial\` L557](../superparser/seman_parser/vector_chart.py#L557) | 1 357 573 | 29,523 s | 63,355 s |
| [\`vector_chart.py:_next_start\` L490](../superparser/seman_parser/vector_chart.py#L490) | 1 060 884 | 3,535 s | 5,637 s |
| [\`features.py:_deref\` L152](../superparser/seman_parser/features.py#L152) | 967 217 | 2,901 s | 4,693 s |
| [\`features.py:unify_values\` L161](../superparser/seman_parser/features.py#L161) | 407 683 | 2,696 s | 8,072 s |
| [\`features.py:unify_structures\` L221](../superparser/seman_parser/features.py#L221) | 133 523 | 2,325 s | 11,879 s |
| [\`vector_chart.py:_add_node_derivation\` L505](../superparser/seman_parser/vector_chart.py#L505) | 187 388 | 1,901 s | 3,092 s |
| [\`vector_chart.py:recognize\` L610](../superparser/seman_parser/vector_chart.py#L610) | 132 | 1,839 s | 66,750 s |
| [\`vector_chart.py:_advance\` L602](../superparser/seman_parser/vector_chart.py#L602) | 464 421 | 1,788 s | 23,209 s |
| [\`vector_chart.py:_LazyMaterializer.get\` L739](../superparser/seman_parser/vector_chart.py#L739) | 77 757 | 1,740 s | 49,782 s |
| [\`vector_chart.py:_get_contextual\` L778](../superparser/seman_parser/vector_chart.py#L778) | 77 757 | 1,732 s | 49,767 s |
| [\`vector_chart.py:_variable_names\` L236](../superparser/seman_parser/vector_chart.py#L236) | 328 824 | 1,642 s | 2,851 s |
| [\`vector_chart.py:_constrained_node_hint\` L1158](../superparser/seman_parser/vector_chart.py#L1158) | 111 323 | 1,516 s | 12,596 s |
| [\`features.py:items\` L97](../superparser/seman_parser/features.py#L97) | 599 904 | 1,434 s | 2,573 s |
| [\`vector_chart.py:_value_key\` L198](../superparser/seman_parser/vector_chart.py#L198) | 445 140 | 1,324 s | 2,084 s |
| [\`vector_chart.py:_compose_rule_context\` L1233](../superparser/seman_parser/vector_chart.py#L1233) | 31 469 | 1,184 s | 8,908 s |
| [\`vector_chart.py:_rule_evidence\` L144](../superparser/seman_parser/vector_chart.py#L144) | 31 469 | 1,163 s | 2,651 s |
| [\`vector_chart.py:_constrained_partial_hint\` L1209](../superparser/seman_parser/vector_chart.py#L1209) | 152 981 | 1,105 s | 12,438 s |
| [\`vector_chart.py:_push_rule\` L940](../superparser/seman_parser/vector_chart.py#L940) | 38 765 | 1,026 s | 37,297 s |

Le temps cumulatif comprend les appels internes et peut se chevaucher entre lignes du tableau. Une même fonction peut être appelée plus d'une fois par phrase; 132 appels à \`recognize\` pour 131 phrases sont possibles selon les chemins de la couche 1.

### Variations CPU de référence

Sur les **19 premières phrases** :
- Parsing canonique sans profileur : **1,424 s CPU**
- Lexicalisation sans profileur : **0,096 s CPU** après chargement initial
- Même parsing avec \`cProfile\` : **9,857 s CPU**. Facteur de ralentissement très élevé : un profilage ne peut pas servir de chronomètre de production.
- Premier accès WordNet sous \`cProfile\` : **12,512 s CPU**, dont 117 659 appels à \`_parse_data_line\`, 155 291 à \`_parse_index_file\`. Il s'agit d'un coût **d'initialisation**, distinct du débit après chargement.

## 3. Ligne par ligne et allocations

Le [premier run](https://github.com/leye0/seman2/actions/runs/39188678707) contient 24 fonctions instrumentées \`line_profiler\`. Parmi les principales lignes de travail :
- \`vector_chart.py:568\`, recherche de l'état partiel par clé;
- \`vector_chart.py:574\`, création du dataclass \`PackedPartial\`;
- \`vector_chart.py:581\`, création d'une \`PartialDerivation\`;
- \`vector_chart.py:595\`, recherche de la prochaine position;
- \`vector_chart.py:620\`, branche de reconnaissance qui appelle \`_add_partial\` (temps inclusif);
- \`vector_chart.py:1221\`, parcours des dérivations contraintes (temps inclusif).

Sur **3 phrases**, le profilage \`tracemalloc\` a observé un pic d'environ **15,5 Mo d'allocations suivies**, surtout dans \`vector_chart.py\` autour des lignes 567–581. Ce pic ne représente ni la consommation totale du processus, ni la pression d'allocations transitoires.

## 4. Tests Python strictement équivalents — 67 phrases, A/B/B/A

Chaque variante a été injectée **en mémoire** dans la même méthode CPython, et jamais enregistrée dans le moteur canonique.

| Variante | CPU mesuré vs base | Intervalle bootstrap du ratio | Justesse |
|---|---:|---:|---|
| Déplacer \`self.text\` et \`len\` vers des variables locales dans \`_next_start\` | −6,50 % | 0,655–1,308 | Identique |
| Remplacer \`dict.setdefault(key, [])\` par \`get\` + insertion uniquement si besoin | −0,02 % | 0,728–1,385 | Identique |
| Éviter le \`tuple()\` au-dessus d'une tranche de liste déjà copiée | −3,95 % | 0,682–1,362 | Identique |

**Conclusion** : aucune de ces trois variantes ne démontre un gain fiable. Toutes préservent la grammaire, mais les intervalles incluent une régression. La variabilité A/A peut atteindre 27 % sur un passage. Ne pas déployer ces modifications seulement sur la foi de ces pourcentages.

Plusieurs phrases identiques ont présenté des temps d'exécution entre ~70 ms et ~250 ms selon leur position dans le cycle, fournissant un signal fort de variabilité extérieure à la logique grammaticale.

## 5. Identification précise du coût GC

### Expérience 1 : GC normal vs collecte manuelle toutes les 8 phrases

67 phrases, ordre A/B/B/A, même nettoyage explicite génération 2 après chaque groupe de 8 dans les deux modes (son temps **inclus** dans les totaux).

| Mode | CPU pendant les parses (moyenne) | Nettoyage complet explicite (moyenne) | CPU total |
|---|---:|---:|---:|
| GC automatique + nettoyage toutes les 8 phrases | 3,900 s | 3,690 s | **7,591 s** |
| GC automatique désactivé pendant les parses + nettoyage toutes les 8 | 1,521 s | 3,716 s | **5,237 s** |

Différence : **−31,0 %**, y compris le coût du nettoyage. Les deux passages de chaque mode restent proches. Mais ces cycles explicites ne font pas partie de l'exécution de production normale : ce protocole sert à **isoler** les collections et leurs coûts, et ce résultat de −31 % **ne peut pas être présenté comme un gain de production**.

Le test observe, par passage :
- mode GC normal : 5 120 collections génération 0, 461 génération 1, **14 génération 2**, dont 9 forcées;
- mode manuel : 9 collections génération 2, toutes forcées;
- coût total observé des GC : environ **6,05 s** en mode automatique contre **3,72 s** en mode manuel.

### Expérience 2 : GC automatique conservé, \`gc.freeze()\` après chargement complet

**Cette expérience est davantage représentative du débit CPU à chaud** : ni le comportement grammatical, ni les règles de collecte automatique du GC ne sont modifiés. La différence testée est seulement le gel temporaire des objets Python déjà vivants avant la phase. Aucune collection forcée *pendant* les parses.

| Passage | GC normal : CPU parse | Freeze : CPU parse |
|---|---:|---:|
| A | 4,958 s | 2,821 s |
| B | 4,956 s | 2,937 s |
| Moyenne | **4,957 s** | **2,879 s** |

**Réduction CPU pendant les parses : 41,9 %**.

Une collection complète est également effectuée *après* chaque passage, mesurée séparément pour ne pas masquer un éventuel transfert de coût. En l'incluant, le CPU total passe de **5,269 s à 3,197 s**, soit **−39,3 %**.

| Compteur du GC / passage | GC normal | Freeze |
|---|---:|---:|
| Objets gelés au début de la passe | 375 (état préexistant) | ~1 256 000 |
| Collections génération 0 | 5 045 | 5 067 |
| Collections génération 1 | 458 | 460 |
| Collections génération 2 | **7** | **37** |
| Temps CPU génération 2 | **2,25 s** | **0,13–0,14 s** |
| Tous GC confondus : CPU | **2,56 s** | **0,43–0,45 s** |
| Valeur max \`ru_maxrss\`, processus partagé | 266 544–266 624 KiB | 266 624 KiB |

Le point saillant est le **coût d'une collection majeure**, pas seulement sa fréquence. Dans cette exécution, \`gc.freeze()\` retire environ **1,25 million d'objets suivis** des scans GC, rendant la génération 2 beaucoup moins chère même lorsque celle-ci est appelée plus souvent.

**Tous les digest des arbres, des alternatives et des compteurs non temporels sont identiques** entre les quatre passages. Aucun signe de régression grammaticale dans cette cohorte.

### Risques et limites de \`gc.freeze()\`

1. \`gc.freeze()\` fige **tous les objets suivis par le GC qui existent à ce moment**, pas exclusivement WordNet. Ce n'est pas un mode par-objet ou par-cache.
2. Les objets gelés ne sont plus collectés cycliquement tant qu'ils restent gelés. Cela peut retenir des objets normalement récupérables, affecter les applications embarquées, et accroître le RSS au fil de longues sessions.
3. L'audit fait \`gc.unfreeze()\` après chaque bras et une collecte complète ensuite. Un déploiement devra vérifier explicitement la gestion des ressources, l'isolation entre parseurs et la mémoire après des milliers de textes.
4. Le RSS fourni par \`ru_maxrss\` est un **maximum global du processus**, pas une mesure fine par configuration. Son quasi-maintien ici **ne prouve pas** l'absence d'accumulation mémoire dans une application persistante.
5. La mesure a lieu **après** la construction des réseaux lexicaux, donc après le chargement paresseux de WordNet. Elle n'inclut pas le coût de la première phrase ni le temps d'initialisation.
6. Un seul type de runner et une seule version de CPython ont été évalués. Une vérification sur machine stable, plusieurs processus frais et une charge long-terme reste nécessaire avant modification de production.

## 6. Conclusion et priorités

### Résultats *démontrés*
- La construction d'états partiels est un hot spot Python central; le moteur exécute ~1,36 million d'appels \`_add_partial\` sur 131 phrases.
- Les trois micro-réécritures testées ne fournissent pas d'amélioration statistiquement défendable.
- Les collections cycliques du GC sont un facteur **majeur** de CPU et de variance, lié à la population très volumineuse d'objets persistants.
- Le gel expérimental des objets préchargés réduit le CPU de parsing de **~42 %** pour cette cohorte sans altérer les résultats.

### Priorité immédiate
**Évaluer la durée de vie et la mémoire du graphe d'objets persistants de WordNet/grammaire, et la façon de séparer les objets immuables durables des objets transitoires pour le GC, sans changer le travail grammatical.** Mesurer en sessions longues et sur plusieurs processus frais. Ne pas appeler \`gc.freeze()\` aveuglément dans un module réutilisable.

### Priorité secondaire
Explorer la réduction de surcharge des appels \`FeatureStructure.items\`, \`_deref\`, \`_variable_names\`, \`_feature_key\` et \`unify_values\` par des microbenchmarks **strictement équivalents et vérifiés**, sans modifier l'ensemble des analyses ni les contraintes.

### Préserver le fonctionnement
Aucun changement permanent dans \`seman_parser/engine.py\`, \`vector_chart.py\`, \`features.py\`, WordNet, grammaires ou données. Seuls les scripts sous \`tools/\` et workflows de mesure ont été ajoutés à \`main\`.

## Scripts reproductibles

- [CPU, ligne, allocations](../tools/cpu_implementation_profile.py)
- [A/B variantes de code Python](../tools/cpu_implementation_ab.py)
- [Coût CPU du GC avec nettoyages contrôlés](../tools/cpu_gc_audit.py)
- [A/B \`gc.freeze()\` à GC automatique conservé](../tools/cpu_gc_freeze_audit.py)

**Notes de méthode** : les pourcentages A/B cités utilisent le CPU sans profileur et ne sont pas dérivés des temps cProfile, qui sont très perturbés par les appels Python. Il faut conserver le niveau d'intégrité des sorties (arbres, alternatives, compteurs) dans tout essai futur.
