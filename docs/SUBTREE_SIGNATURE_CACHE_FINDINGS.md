# Cache de signatures de sous-structures : résultats et limites (18 octobre 2026)

**Dépôt :** `leye0/seman2`. **Branche :** `main`. **Statut : prototype de recherche observateur, désactivé dans le parseur canonique.** Aucun corpus ni aucune règle n'a été modifié.

## Pourquoi cette expérience ?

Nous avons obtenu, avec le **Layer 1 à routage adaptatif** (complexité évaluée *avant* le parsing), un premier gain de CPU de ~15,6 % sur 128 phrases stratifiées de quatre romans nettoyés. Le moteur alternatif `lazy_trie_recognition` économise la reconnaissance des préfixes communs et ne crée les états individuels que lorsque le `k-best` en a besoin. Le chemin canonique des phrases simples, les lectures lexicales multiples et le chemin des dialogues restent protégés. Les phrases saturées demeurent non certifiées malgré la concordance des meilleurs arbres mesurés : ne PAS activer ce mode par défaut.

La question posée ensuite : peut-on réutiliser notre **ancien cache de signatures grammaticales extrêmement rapide**, développé lors des travaux de `Full-Structure Snapping`, également à l'intérieur de phrases longues ?

**Ancien travail retrouvé** dans `archive/legacy-parsers-2026-10-18` :
- `superparser/research/verbnet_lr/full_structure_snap.py` ;
- `superparser/research/verbnet_lr/compiled_structure_snap.py` ;
- `superparser/scripts/benchmark_snap_novels_online.py` ;
- `superparser/research/verbnet_lr/FULL_STRUCTURE_SNAPPING_FINDINGS.md` (conservé sur `main`).

L'ancien cache fonctionnait avec des **arbres complets** et pouvait réutiliser les patrons lexicalement compatibles. Il avait montré des gains de vitesse sur certaines séries, **mais aussi des acceptations grammaticales incorrectes** en l'absence de garde-fous, de la faible généralisation hors distribution et des doutes quant à l'exhaustivité du `k-best`. **Ne jamais reprendre son acceptation directe sans revalider tous les traits, dépendances, `requires`, portées et règles.**

## Ce qui a été implémenté aujourd'hui

`superparser/research/verbnet_lr/subtree_signature_cache.py` :
- `SubtreeSignatureCache.observe(tree, lattice)` enregistre, pour chaque sous-arbre *complètement matérialisé par le parseur canonique*, des séquences de **catégories lexicales** avec la **forme intégrale de son arbre de règles**. On conserve toutes les distinctions de `rule_id` et d'attachements.
- Les patrons mémorisés n'incluent **aucun mot, lemme, nom propre ni texte brut**. Ils sont limités à des sous-structures de **2 à 8 tokens** complètement alignées, à raison d'une feuille lexicale par token. Multiwords, sous-spans non alignés, interfaces sans preuve et couvertures incomplètes sont rejetés.
- `SubtreeSignatureCache.scan(lattice)` teste chaque position dans une phrase plus longue. L'index est un **trie de catégories**. Il accepte plusieurs lectures grammaticales par token, **sans énumérer leur produit cartésien**. Budgets : maximum 25 000 transitions / 2 000 suggestions par requête.
- `freeze()` empêche les données évaluées d'être utilisées pour l'apprentissage. Une observation répétée garde le même patron ; différentes structures sous la même signature conservent **des identités de modèles distinctes**.
- Une suggestion `SignatureHint` donne `start/end`, catégorie racine et `root_rule`. **Ce n'est pas une phrase reconnue ni une preuve grammaticale**. Elle ne fabrique aucun `ForestNode`, n'élimine aucune candidate lexicale, ne produit aucune interprétation sémantique et ne court-circuite pas le parseur. Une structure similaire peut avoir des traits incompatibles.
- `witnessed_matches` compte uniquement les suggestions dont **l'arbre intégral de règles et de catégories** est retrouvé dans le **meilleur arbre du corpus de test**, si celui-ci a effectivement été matérialisé. Ce n'est **pas une vérité grammaticale humaine** et cela n'invalide pas les autres suggestions.

`superparser/tests/test_subtree_signature_cache.py` vérifie les homonymies lexicales, les attaches distinctes, l'absence de faux succès grammaticals, le plafonnement, la congélation, la conservation du réseau lexical et le rejet des multiwords non alignés. Le workflow de validation de base est vert : **145 tests** le 18/19 octobre 2026, `https://github.com/leye0/seman2/actions/runs/39179144930`.

## Premier audit réel : consultation rapide, potentiel de partage

Code : `superparser/scripts/benchmark_subtree_signature_cache.py`.
Workflow : `.github/workflows/subtree-signature-cache.yml`, lancé une fois, puis **`workflow_dispatch` seulement** pour éviter de dépenser des minutes Actions inutilement.

[Action réussie n° 39179311656](https://github.com/leye0/seman2/actions/runs/39179311656) ; [archive des diagnostics par phrase](https://github.com/leye0/seman2/actions/runs/39179311656/artifacts/12155931369).

Protocole : 4 romans nettoyés déjà suivis dans le dépôt ; `choose_cases(12)` stratifié en quatre bandes de longueur. Entraînement uniquement sur des phrases **sans guillemets de 4–16 tokens**, dont l'analyse canonique complète fournit les sous-arbres. Chaque livre évalué est **strictement exclu de son propre cache** : on apprend avec les **trois autres**. Évaluation sur les phrases de **17–32 tokens sans guillemets** ; lexique WordNet 3.0 ; `max_items=20_000`, `kbest_work_limit=100_000`. Les textes d'entraînement ne sont pas sauvegardés dans le cache. Ces quatre romans ont déjà été utilisés dans les recherches de Seman2 : **ce n'est pas un test externe vierge**.

| Mesure | Résultat |
| --- | ---: |
| Phrases longues effectivement évaluées | **67** |
| Modèles distincts par livre exclu | **92 à 101** |
| Phrases comportant au moins une signature connue | **67/67** |
| Suggestions émises au total | **1 511** |
| Spans distincts portant une ou plusieurs suggestions | **936** |
| Consultations arrêtées par le budget du trie | **0** |
| Coût CPU total du balayage de signatures | **12,65 ms / 67 phrases** |
| Coût CPU médian | **0,181 ms** |
| Coût CPU p95 | **0,274 ms** |
| Temps CPU total du parseur canonique sur ces phrases | **13,92 s** |
| Analyses canoniques complètes pour vérifier la forme de l'arbre | **30/67** |
| Épisodes de saturation de la forêt canonique | **31/67** |
| Suggestions retrouvées **dans les meilleurs arbres** des cas analysables | **109** |

Le coût brut du balayage représente environ **0,09 %** du coût CPU du parseur canonique de ce petit lot (12,65 / 13 921 ms), **avant toute réutilisation**. C'est encourageant pour un index consultable à l'entrée du chemin difficile. **Ce chiffre n'est PAS une accélération : on ajoute actuellement le coût de lecture au parsing original.**

**Point essentiel : 67/67 ne veut absolument pas dire 100 % de validité.** Les motifs courts comme `DET N` sont fréquents. Parmi les 1 511 suggestions, seulement 109 ont été *observées* dans les meilleurs arbres des phrases complètes, et les 37 phrases non complétées ne permettent pas de validation équivalente. Le dénominateur « toutes les suggestions utiles et correctes » reste **inconnu**. Il faudra classer les signatures plus informatives et vérifier leurs contraintes avant toute économie de calcul.

## Raccordement correct à l'architecture adaptative

La conception cible reste :

1. **Lattice lexical complet** (mots originaux, catégories, sous-types, traits, offsets, alternatives).
2. **Routage préparse** : phrases simples → parseur canonique sans scan supplémentaire ; dialogues → chemin spécialisé canonique tant que leur routage n'est pas certifié.
3. Phrase jugée difficile → `SubtreeSignatureCache.scan` pour trouver, à très faible coût, les **sous-structures potentielles** déjà observées, avec leurs `start/end`, `root_rule` et *forme de règles*.
4. **Prochain code non encore implémenté : vérificateur de patron contextualisé** : reconstituer la dérivation de chaque patron candidat dans le *nouveau* lattice, avec les *mêmes* règles, combinaisons de sens lexicaux, unification des traits et vérifications `requires` que le `_LazyMaterializer` actuel. Une signature seule ne suffit JAMAIS.
5. **Prochain code non encore implémenté : véritable réutilisation** : introduire uniquement les sous-arbres ainsi prouvés comme constituants structurés dans le `LazySharedTrieForest`, en préservant *toutes* les variantes de la forêt et leur ordre. Une amorce rapide ne doit ni déclarer les autres analyses impossibles, ni décompter fictivement les États partagés du plafond historique de 20 000.
6. Comparer **A / hybride / A** sur les **mêmes phrases**, p50/p95/p99, temps de reconnaissance, `k-best`, score et morphosyntaxe, dérivations ordonnées, sens lexicaux et **peak RSS** ; premiers contrôles stricts sur les forêts non saturées, et preuves de sécurité spécifiques sur les saturations. Seules les améliorations CPU nettes, y compris les ratés de cache, peuvent être activées par défaut.

## Les pièges qu'il ne faut pas reproduire

- Ne pas décrire un `SignatureHint` comme un parse. Une séquence de catégories ne prouve **ni structure, ni valence, ni accord**.
- Ne pas pousser directement l'ancien `FullStructureSnapIndex` dans `main` : il dépend d'anciens moteurs supprimés et ses vieux résultats ont montré des risques de faux positifs.
- Ne pas ralentir les phrases simples avec une consultation inconditionnelle du cache.
- Ne pas entraîner le cache depuis l'évaluation (même implicitement, après un passage raté) ; geler les trois livres d'entraînement.
- Ne pas confondre la correspondance de **forme** avec l'identité des **entités/sens**. Transporter les feuilles originales au Layer 2.
- Ne pas confondre 88,3 % de préfixes groupables (ancien audit) avec 88,3 % de temps économisé.
- Ne pas dépasser silencieusement le budget d'analyse, modifier les textes des corpus ou supprimer les guillemets des romans.
- Éviter une nouvelle boucle de prototypes de stockage après l'échec mesuré des couches `indexed` et `online_prefix_edges`.
- **Ne pas annoncer une accélération supplémentaire issue du cache** avant d'avoir effectivement raccourci le travail de reconnaissance tout en retrouvant les mêmes analyses.

## Reproduire et reprendre

```bash
# À la racine du dépôt. WORDNET_DICT doit pointer au répertoire dict/ WordNet 3.0.
WORDNET_DICT=/chemin/wordnet/dict PYTHONPATH=superparser \
  python -m unittest -v superparser.tests.test_subtree_signature_cache

WORDNET_DICT=/chemin/wordnet/dict PYTHONPATH=superparser \
  python superparser/scripts/benchmark_subtree_signature_cache.py \
    --wordnet-dir "$WORDNET_DICT" --per-book-per-band 12 \
    --max-signature-tokens 8 \
    --out-dir /tmp/seman2-subtree-signatures
```

L'Action peut être redéclenchée manuellement : `Research — Observed Subtree Signature Cache`.

**Critère de décision du prochain essai :** comparer des suggestions longues/structurées (p. ex. ≥4 mots, plusieurs règles, témoins best-tree) aux suggestions courtes pour filtrer les faux espoirs de cache ; puis créer un vérificateur de dérivation autonome non circulaire, sans jamais accepter une analyse à partir du trie de signatures seulement. Si le coût de validation est supérieur au coût de la reconnaissance actuelle, abandonner ce raccourci et documenter l'échec.

Le gain CPU de **15,6 % sur 128 phrases** provient de notre **moteur à préfixes partagés + routage adaptatif**, PAS de ce nouveau cache. Le cache n'est qu'un candidat à une amélioration supplémentaire.
