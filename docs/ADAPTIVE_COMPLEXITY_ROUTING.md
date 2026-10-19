# Routage adaptatif — la seule optimisation conservée

**Source d'exécution : [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md).** Statut : opt-in; défaut : canonique.

## Contrat obligatoire

`ComplexityPolicy(rule_start_threshold=..., min_tokens=17, difficult_strategy="trie")` est la **seule** politique autorisée. Le moteur a **exactement deux chemins** : `_VectorForest` canonique, et `LazySharedTrieForest` déclenché pour les phrases longues non citées au risque préparse élevé. Les guillemets/dialogues empruntent une grammaire canonique spécialisée. Le système NE DOIT PAS ralentir les courtes phrases en calculant une signature qui ne servirait à rien.

Le score compilé est `fast_start_sum`, somme des nombres de règles susceptibles de commencer aux différentes positions en fonction de **toutes** les catégories lexicales candidates. Il utilise des masques entiers précalculés sur les règles actuelles, **ne regarde aucun résultat du parsing**, et ne produit ni arbre ni reconnaissance.

Les bandes de longueur et le seuil sont des entiers fournis par l'appelant. `rule_start_threshold=1` dans `scripts.smoke_layer1.py` est un **seuil de test volontairement artificiel**, uniquement pour forcer le branchement et en vérifier le fonctionnement. Il ne doit jamais devenir la configuration implicite de production.

## Résultats historiques suffisants pour comprendre notre choix

- La première approche consistait à dédoubler la reconnaissance par règle et à compresser les preuves ensuite. Elle demandait parfois **2,4 fois** plus de temps CPU; échec malgré des économies mémoire.
- Le saut de simples vérifications de catégorie dans un algorithme `indexed` n'a pas démontré de gain, même avec collecte des déchets contrôlée (les 11 cas lourds sont restés ~2,45 % plus lents).
- L'automate de préfixes communs, avec matérialisation paresseuse des états propres aux règles, a au contraire livré **−43 % CPU** lors d'un essai autonome sur 42 longues phrases.
- **Benchmark adaptatif complet**, Action [39177896708](https://github.com/leye0/seman2/actions/runs/39177896708) : canonique ~5,13 s, adaptatif ~4,33 s CPU sur 128 phrases, soit ~**−15,6 %**, avec 32 phrases routées et 96 canoniques, dont 64 courtes sans prédiction. Les deux passages canoniques A/A étaient pratiquement identiques.
- Seuls **13/32** cas routés non saturés ont bénéficié d'une comparaison de toutes les dérivations; les **19** cas saturés étaient non certifiés, même si leurs arbres comparés concordaient.
- Un cache additionnel de dérivations lazy au moment du `k-best` n'a pas amélioré ce gain et a été annulé.

Les mesures ne se généralisent pas à de nouveaux auteurs sans benchmark contrôlé. Les scores de risque sur une bande de longueurs ne constituent pas une preuve que le trie réduira la latence de toute phrase difficile.

## Comment mesurer sans rouvrir les anciens projets

- `superparser/scripts/benchmark_adaptive_routing.py` : unique mesure A/adaptatif/A des deux moteurs courants; temps CPU, reconnaissance, `k-best`, analyses complètes et dérivations des forêts non saturées.
- `superparser/scripts/corpus_samples.py` : échantillonnage déterministe des quatre romans nettoyés.
- `.github/workflows/layer1-adaptive-benchmark.yml` : **exécution manuelle seulement** pour économiser les minutes GitHub Actions.

Nos prochaines priorités sont **la justesse, l'exhaustivité des alternatives et la couverture** dans les phrases lourdes, pas un autre mode de stockage ou d'indexation. Voir [KNOWN_LIMITS_AND_ROADMAP.md](KNOWN_LIMITS_AND_ROADMAP.md).
