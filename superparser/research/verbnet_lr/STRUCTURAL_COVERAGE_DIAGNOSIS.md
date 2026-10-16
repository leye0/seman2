# Seman2 — audit des échecs sur phrases longues (16 octobre 2026)

**Branche exclusivement expérimentale :** `research/verbnet-left-to-right-poc`.
**CI de référence :** [GitHub Actions #38921873433](https://github.com/leye0/seman2/actions/runs/38921873433).
**Rapports :** [long_stress_report.json](long_stress_report.json), [grammar_upper_bound.json](grammar_upper_bound.json), [grammar_quality_gate.json](grammar_quality_gate.json).

## Résultat falsifiable

Sur les **8 phrases stress longues** (31–65 mots, aucun arbre gold) :

- Le lecteur gauche-droite Seman2 complète **0/8**.
- La reconnaissance CFG *permissive, sans traits* complète **8/8** en conservant le même réseau lexical par token et les catégories de la grammaire courante.
- Aucun token n'est sans candidat lexical dans ces huit phrases. Cela **ne** garantit pas que les candidats contiennent la *bonne* catégorie pour le contexte.
- Le reconnaisseur hors ligne explore de **58 659 à 284 415 items** par phrase et demande environ **85–791 ms**, sans arbre, sans unification ni contraintes de valence. **Ce n'est pas un parseur temps réel** et ces temps ne sont pas comparables à l'objectif de 5 ms.
- Le corpus externe UD English-EWT demeure un garde-fou : les variantes expérimentales précédentes n'y complètent qu'environ **1/32** phrase. Les constructions de notre petit corpus interne ne prouvent pas la généralisation.

**Conséquence précise :** le problème n'est pas l'absence nécessaire d'une dérivation *catégorielle* pour ces huit phrases. Il reste possible que **toutes** les dérivations trouvées par l'oracle permissif échouent à l'unification des traits ou soient syntaxiquement aberrantes. Ne pas annoncer que « la grammaire sait correctement analyser 8/8 ».

## Témoins d'échec concrets (issus des piles avant restauration)

| Famille | Témoins | Ce qu'observe le code |
| --- | --- | --- |
| Frontières d'attachement | stress_01, stress_06 | `NP → WH-OBJ → NP` peut absorber une suite qui devrait être examinée par des ancêtres ; arrêts sur `because` ou `would`. |
| Relatives et périphrases verbales | stress_02, stress_07 | Après `which`, l'analyse demande `VP-NP` alors que le prochain mot possède `HAVE/V` (ex. `had been…`). |
| Mauvaise sélection morphosyntaxique | stress_03 | `could be repeated` peut emprunter un chemin `MODAL → V(be) → NP` au lieu d'une construction passive adaptée. |
| Coordination | stress_04 | `so` possède ici `ADV/DEGREE/N`, pas `COORD` ; le lecteur tente `VP` après une virgule. Une couverture lexicale non vide n'est pas une preuve du bon POS. |
| Complétive interrogative | stress_05 | `how` peut être consommé comme `WH-CLAUSE` atomique, laissant `the engineers…` non rattaché. |
| Adjonction temporelle | stress_08 | `earlier`, pourtant `ADJ/ADV`, rencontre une attente `PP` issue d'une autre segmentation de `several minutes`. |

Les piles et leurs essais successifs sont maintenant exportés sous `diagnostics[*].stack_failures` dans `long_stress_report.json`. L'instrumentation est **optionnelle et hors fenêtre chronométrée**.

## Décision architecturale

1. **Ne pas multiplier les reprises ni les règles par phrase.** La limite de trois checkpoints fait échouer huit phrases, mais augmenter naïvement le budget a déjà coûté de la latence sans complétion générale.
2. **Séparer trois causes :** (a) absence de dérivation catégorielle ; (b) dérivation catégorielle présente, mais impossible avec les traits/licences/valences ; (c) dérivation valide existante, mais manquée par le lecteur monotrajets. Cet audit élimine (a) sur ce corpus, **pas** (b).
3. **POC suivant : vérificateur de témoins avec traits, hors ligne.** Réutiliser le moteur d'unification existant pour vérifier une sélection bornée de dérivations de l'oracle CFG, produire des spans, rôles syntaxiques, accords et une raison explicite d'échec. L'absence de témoin dans un budget doit donner `UNKNOWN` et jamais « agrammatical ».
4. **Seulement si un témoin valide existe :** expérimenter le guidage du lecteur par des preuves structurelles compactes (frontière du constituant, attentes du parent/ancêtre, séquences lexicales nécessaires), sans forêt en mémoire d'exécution, et mesurer sur dev/validation/holdout indépendant + négatives + EWT.
5. **Conditions de succès :** augmentation des analyses conformes, aucune nouvelle négative acceptée, aucune régression de conformité, puis médiane proche de 5 ms et p95 surveillé. Un arbre complet mais faux ne compte jamais comme réussite.

**Statut : diagnostic confirmé en CI, aucune promotion au runtime de production, aucun changement à `main` ou `grammar.jsonl`.**
