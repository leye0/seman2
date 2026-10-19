# Limites actuelles et feuille de route — seul Layer 1

**État de main après nettoyage.** Le code à exécuter est décrit dans [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md). Les anciennes expériences sont archivées dans Git, pas dans notre API.

## Ce qui reste difficile

- **Exactitude et complétion différentes :** une analyse complète peut être grammaticalement erronée (accord, valence, rattachement, coordination, temps, dialogue). Un parse réussi n'est pas une validation humaine.
- **Forêts saturées :** sur des phrases longues, le plafond de 20 000 états peut être atteint; la limite de travail du `k-best` est distincte. Un budget épuisé n'est pas une preuve d'agrammaticalité.
- **Deux voies seulement :** canonique par défaut; trie à préfixes communs et projection lazy seulement avec une politique préparse explicite. Sous `min_tokens`, aucune signature n'est calculée. Les dialogues restent sur leur grammaire spéciale.
- **Performance contextualisée :** dans l'Action [39177896708](https://github.com/leye0/seman2/actions/runs/39177896708), 128 phrases de quatre romans : 5,13 s CPU canonique contre 4,33 s adaptatif, **−15,6 % sur cette cohorte**, dont 32 phrases routées. Ce chiffre ne prouve pas un gain pour d'autres auteurs, ni un gain de justesse.
- **Saturations non certifiées :** 13 des 32 cas routés et non saturés avaient des preuves complètes comparées; les 19 cas saturés ne possèdent pas encore de preuve générale d'identité exhaustive, même si leurs arbres comparés concordaient. L'alternative reste opt-in.
- **Dialogues et segmentation :** guillemets, initiales et dialogues de romans sont préservés, mais toutes les incises, citations non équilibrées et formes discursives ne sont pas encore correctement analysées.
- **Généralisation :** seuls quatre romans historiquement étudiés ont servi de base à ces recherches. De nouveaux auteurs et des exemples positifs/négatifs annotés seront nécessaires.
- **Layer 2 :** nous transmettons les mots, traits, spans, règles et structures. La mémoire épisodique, la coréférence persistante et l'apprentissage sémantique restent futurs et ne font pas partie de ce dépôt.

## Ce que l'utilisateur veut développer ensuite

**Pause explicite des nouvelles méthodes d'optimisation, patterns et caches.** Ne pas réintroduire les anciens moteurs supprimés. Nous améliorons **le Layer 1 existant** en traitant ses erreurs grammaticales et ses trous de couverture, sur les vraies phrases difficiles.

Étapes :
1. Vérifier les trois parcours (canonique court, trie lazy opt-in long, dialogues) et les tests décrits dans [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md).
2. Séparer les vraies phrases littéraires des citations, initiales, erreurs de découpage, absences de règles, saturations de forêt et épuisement du `k-best`.
3. Corriger les règles, sous-types et accords de façon ciblée; préserver les succès connus et créer des fixtures positives ET négatives.
4. Garder tous les lexèmes originaux, les catégories alternatives, les traits, les preuves `requires`, les offsets et les dépendances syntaxiques pour le futur Layer 2.
5. Mesurer couverture, **justesse** et budgets sur un corpus figé avec auteurs inédits; ne jamais augmenter artificiellement la couverture en affaiblissant les contraintes.

Voir [RESEARCH_HISTORY_AND_DECISIONS.md](RESEARCH_HISTORY_AND_DECISIONS.md) pour les résultats négatifs et la branche [archive/pre-simplification-2026-10-18](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18) pour leur ancien code.
