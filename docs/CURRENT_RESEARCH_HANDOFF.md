# Seman2 — POINT DE REPRISE POUR UNE NOUVELLE CONVERSATION

**Mise à jour : 18 octobre 2026 (les CI GitHub ont des horodatages UTC du 19).** Lire CE fichier d'abord, puis la documentation ci-dessous. **Travail directement sur `main`** du dépôt privé `leye0/seman2` via plugin GitHub, sauf instruction contraire.

## Quel projet et quelles exigences ?

Notre objectif est un **Layer 1 grammatical rapide et fidèle**, qui transmet au futur Layer 2 l'arbre (et ses alternatives), les **mots originaux**, offsets, catégories/sous-catégories, traits, lexical candidates et provenance. Le Layer 2 s'occupera des interprétations, entités et épisodes ; aucun faux souvenir grammatical ne doit être enregistré.

**Contrainte INVIOLABLE du propriétaire : « prédire d'abord, router ensuite ».** Les phrases simples doivent conserver le parseur canonique rapide sans payer pour le moteur lourd. Les phrases complexes utilisent un score préparse de pression des débuts de règles compilés (`StructuralRiskRouter`) et un seuil de longueur explicite (minimum 17 tokens dans nos pilotes) ; les dialogues conservent leur grammaire spécialisée. Les seuils sont opt-in, aucune promotion implicite en production.

**Les romans Gutenberg nettoyés, WordNet, et toutes les ressources de corpus conservées doivent rester intacts.** Le nettoyage du dépôt et l'archive des anciens moteurs ont déjà été fusionnés. Les scripts de recherche historiques se trouvent en partie sous `archive/legacy-parsers-2026-10-18` et dans les fichiers `RESEARCH_HISTORY_AND_DECISIONS` / `CLEANUP_MANIFEST`. Wikipédia n'a pas été localisé dans les fichiers suivis de `main` lors du ménage ; ne pas prétendre l'avoir supprimé.

## Quelle est la version de référence fiable ?

`superparser/seman_parser/engine.py` : `Parser` canonique et son chemin alternatif `ComplexityPolicy(..., difficult_strategy="trie")`, explicitement désactivé par défaut. `superparser/seman_parser/vector_chart.py` et `lazy_trie_forest.py` : automate de préfixes partagés avec matérialisation paresseuse des `PackedPartial` pour le `k-best`. `complexity_routing.py` : score du routeur préparse ; court-circuit pour les phrases faciles.

Sur **128 phrases**, le **système adaptatif existant** avait donné 5,13 s CPU canonique contre **4,33 s CPU adaptatif** (gain **15,6 %**) dans [l'Action 39177896708](https://github.com/leye0/seman2/actions/runs/39177896708) : 32 phrases routées, 96 canoniques, 64 très courtes sans prédiction. Les 13 forêts routées non saturées avaient des dérivations équivalentes ; **19 forêts saturées n'étaient pas pleinement certifiées** même quand leurs arbres comparés concordaient. Un cache supplémentaire des dérivations lazy `k-best` avait donné un résultat moins bon et a été annulé. Aucune prétention que les grandes phrases sont toutes résolues.

## Ce qui vient d'être essayé : ancien cache de signatures → sous-structures

L'utilisateur a demandé si notre ancien **cache de signatures très rapide**, utilisé en recherche pour les phrases simples, pouvait accélérer nos **phrases longues**. Il a demandé une expérimentation et une documentation suffisante pour continuer dans une autre conversation.

Ancien code archivé : `archive/legacy-parsers-2026-10-18/superparser/research/verbnet_lr/full_structure_snap.py` et `compiled_structure_snap.py`. Les vieux résultats de snapping montrent des hits en microsecondes **mais aussi des faux positifs** si l'on accepte une signature sans valider le patron complet. **NE PAS restaurer les anciens lecteurs de manière indiscriminée.**

**Nouveaux fichiers sur `main` :**
- `superparser/research/verbnet_lr/subtree_signature_cache.py` — `SubtreeSignatureCache.observe`, `freeze`, `scan`, `witnessed_matches`. Index de séquences de catégories lexicales de sous-arbres **déjà feature-validés par le parseur**, avec leurs formes complètes de règles, sans stocker les mots. Scan O(longueur × largeur de trie) borné, tenant compte des alternatives POS. **HINT UNIQUEMENT.**
- `superparser/tests/test_subtree_signature_cache.py` — tests d'ambiguïté, du corpus intact, du budget, de la congélation et de la distinction des structures.
- `superparser/scripts/benchmark_subtree_signature_cache.py` — apprentissage sur les trois autres romans, évaluation sur longues phrases du quatrième, statut des analyses, temps de scan et témoins d'arbres.
- `.github/workflows/subtree-signature-cache.yml` — benchmark manuel uniquement après son premier lancement.
- `docs/SUBTREE_SIGNATURE_CACHE_FINDINGS.md` — rapports, décisions et consignes détaillées.

**Action [39179311656](https://github.com/leye0/seman2/actions/runs/39179311656) verte :**
- **67 longues phrases** admissibles (17–32 tokens, sans guillemets) ; **67/67** avec au moins une suggestion ; **1 511** suggestions sur **936** spans.
- **92–101** modèles distincts appris dans les autres romans.
- Scan médian CPU **0,181 ms**, p95 **0,274 ms**, CPU total **12,65 ms** / 67 phrases, contre **13,92 s** pour leur parsing canonique.
- **30** analyses complètes ; **109** suggestions retrouvées dans les sous-arbres des meilleurs arbres (n'est PAS du gold). **31** saturations ; pas de conclusion grammaticale sur les autres suggestions.
- **145 tests core verts** [Action 39179144930](https://github.com/leye0/seman2/actions/runs/39179144930).

**Interprétation cruciale :** la consultation est rapide mais **ne produit AUCUN gain** actuellement puisqu'elle ne fait que renvoyer des `SignatureHint`. Le 67/67 est trompeur : les petits motifs grammaticaux sont omniprésents, une suggestion n'est pas une preuve d'analyse. Nous n'avons PAS encore raccordé le cache au `LazySharedTrieForest` pour éviter de la reconnaissance.

## Action concrète attendue dans la prochaine conversation

1. Revoir `docs/SUBTREE_SIGNATURE_CACHE_FINDINGS.md` et [le rapport de l'Action 39179311656](https://github.com/leye0/seman2/actions/runs/39179311656). Vérifier `main` avant toute écriture.
2. **Mesurer quels patrons sont vraiment utiles** : hit rate et présence effective dans un arbre feature-validé en fonction de la longueur (2–3 vs 4–6 vs 7–8), du nombre de règles, du gain théorique et du coût de scan. Ne pas entraîner avec le livre évalué. Élargir au-delà de quatre vieux romans pour la généralisation.
3. Construire un **replayer feature-aware** d'un sous-arbre observé sur un autre span, en utilisant exactement les règles courantes, l'unification, les `requires`, les contextes de variables et toutes les alternatives lexicales. Sans preuve, le hit est rejeté ; il ne doit pas forcer une analyse.
4. Seulement ensuite expérimenter une **réutilisation incrémentale** dans le `LazySharedTrieForest` : commencer par les sous-arbres possédant une preuve exhaustive et une compatibilité complète, préserver les variantes de règles, l'ordre d'énumération, le `k-best`, les offsets et les mots. S'il est impossible de préserver la couverture et le budget à 20 000 états, laisser la fonction en lecture seule.
5. Benchmark A / cache+trie / A sur les **mêmes longues phrases**, avec coûts de hit et MISS, CPU+RSS, non-régression grammaticale stricte sur les forêts non saturées et décision honnête sur les saturées ; jamais de ralentissement du chemin canonique. Garder une option explicitement opt-in.
6. Enregistrer décisions, liens de CI, validations, échecs et SHA du nouveau `main` ICI afin que la prochaine conversation ne recommence pas d'anciens prototypes.

## Outils et discipline

Utiliser le plugin GitHub connecté, dépôt `leye0/seman2`, branche `main`, outil `functions.exec` et fonctions `mcp__GitHub__fetch_file`, `create_tree`, `create_commit`, `update_ref`, `fetch_workflow_run_jobs`, `fetch_workflow_job_logs`. Quand plusieurs fichiers changent, préférer un commit atomique créé à partir du dernier `main` et un déplacement de ref avec `expected_sha`. Exécuter les tests avant de déclarer un succès.

Les Actions coûtent des minutes ! Les grands benchmarks doivent être en `workflow_dispatch` **manuel** après une seule exécution d'investigation. Le noyau peut continuer ses tests à chaque modification de parser/tests. Toujours documenter les **résultats négatifs**, pas seulement les améliorations et ne jamais « gagner » en perdant des dérivations.

Lire aussi :
- `docs/ARCHITECTURE_LAYER1.md`
- `docs/ADAPTIVE_COMPLEXITY_ROUTING.md`
- `docs/CATEGORY_PREFIX_TRIE_FINDINGS.md`
- `docs/RESEARCH_HISTORY_AND_DECISIONS.md`
- `docs/KNOWN_LIMITS_AND_ROADMAP.md`

**Phrase de reprise à copier :** « Continuons Seman2 directement sur main en lisant docs/CURRENT_RESEARCH_HANDOFF.md et docs/SUBTREE_SIGNATURE_CACHE_FINDINGS.md. Nous avons prouvé que le cache de sous-structures trouve vite des signatures dans les phrases longues, mais il ne réutilise pas encore ces structures. Notre priorité est de mesurer les signatures vraiment utiles puis de construire un replayer feature-validé, sans faux positifs ni ralentissement du chemin canonique. »
