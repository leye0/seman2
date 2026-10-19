# Architecture du Layer 1 actuellement supportée

**Document actif**, complément de la [notice d'exécution](RUN_CURRENT_LAYER1.md). Il n'existe plus de moteurs alternatifs historiques dans `main`.

## Objet

Le Layer 1 de Seman2 analyse grammaticalement des phrases **en anglais** sans effacer les mots originaux. Il transforme le texte en :

- `LexicalLattice` : tokens avec texte original et offsets, plusieurs candidats (catégorie, sous-catégorie, traits, sens, provenance) par portée.
- Forêt grammaticale : catégories et états de règles reconnus sous un plafond explicite; une forêt incomplète ne constitue pas une preuve d'agrammaticalité.
- Analyses `ChartItem` accessibles par `ParseResult.best()` et `alternatives(limit=k)`, avec leurs enfants, règles, contraintes unifiées et informations syntaxiques.
- Relations sémantiques dérivées par les recettes actuelles de `semantics.py` / `semantic_rules.py`, **après** le choix des analyses. Les entités persistantes, souvenirs et apprentissage sémantique du futur Layer 2 sont hors du dépôt courant.

## Chemin 1 : canonique — TOUJOURS le défaut

```
Parser(resources).parse(text)
 → tokenize / build_lattice (segmentation.py)
 → VectorGrammar (vector_chart.py)
 → _VectorForest.recognize
 → _LazyMaterializer (k-best)
 → ParseReport / ParseResult
```

Le parseur canonique ne calcule **aucune signature de complexité**. L'ensemble des alternatives du lattice lexical est conservé; le système ne « simplifie » pas le texte pour améliorer artificiellement les statistiques.

## Chemin 2 : adaptatif — EXPLICITEMENT configuré

```
Parser(resources, complexity_policy=ComplexityPolicy(...))
 → le même LexicalLattice
 → StructuralRiskRouter.choose (avant le parser)
    ├─ courte (< min_tokens) ⇒ CANONIQUE, zéro score
    ├─ citation/dialogue     ⇒ grammaire canonique des dialogues
    ├─ score < seuil         ⇒ CANONIQUE
    └─ score ≥ seuil         ⇒ VectorGrammar(lazy_trie_recognition=True)
                               → LazySharedTrieForest
                               → _LazyMaterializer identique
```

Le score de risque est une **pression des débuts de règles grammaticales** à partir des catégories possibles de chaque token. C'est une heuristique de coût, **pas un verdict grammatical**, ni une probabilité de correction. Les seuils et bandes de longueurs doivent être fournis explicitement; aucun cutoff de production n'est recommandé aujourd'hui.

Le trie est préparé par `shared_trie_forest.py`, qui ne définit **pas** une variante exécutable distincte. `lazy_trie_forest.py` reconnaît les préfixes communs par groupe/catégorie/span, conserve les variantes de règles, et ne construit les objets de partials originaux que si le `k-best` les demande. La matérialisation utilise toujours les contraintes `features`, `requires`, variables et actions des règles originales.

## Dialogues

`sentence_boundaries.py` conserve les phrases et guillemets (y compris les initiales avec points). `dialogue.py` superpose les frontières de citation et `data/dialogue_grammar.jsonl` dans son cadre limité. Le canonique reçoit le texte inchangé pour les dialogues. Un guillemet brisé ou une citation littéraire n'est pas automatiquement un arbre reconnu.

## Limites architecturales

Les passages de recherche ont montré un **gain CPU global de 15,6 %** sur une cohorte précise de 128 phrases avec 32 phrases routées. Sur les 19 forêts saturées parmi ces cas routés, l'identité complète de toutes les dérivations n'était pas encore certifiée; **ne pas activer le trie par défaut et ne pas annoncer de gain de couverture en cas de saturation**. La lecture correcte d'un roman exige encore des améliorations des règles, de la ponctuation, des analyses négatives et des unités syntaxiques longues.

Les anciens caches de signatures, indexations de stockage, scénarios d'induction, moteurs GLR / C et traitement de coref/discours ne sont plus des fonctions du dépôt courant. Voir [historique des décisions](RESEARCH_HISTORY_AND_DECISIONS.md).

## Contrat de qualité

1. **Zéro perte** des mots, guillemets, alternatives lexicales, sous-types, offsets et traits.
2. **Ne pas** assimiler un succès de complétion à une analyse humaine correcte.
3. Vérifier les cas positifs ET négatifs, les alternatives `k-best`, les ancres syntaxiques et la sémantique après projection.
4. Respecter les plafonds des états du canonique comme référence honnête, même avec des groupes partagés.
5. Le Layer 2 doit recevoir l'information originale et la structure, pas un résumé élagué.

Pour les commandes de vérification véritables, suivre [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md), ou directement la CI `.github/workflows/core-seman2-validation.yml`.
