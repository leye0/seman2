# Seman2 — preuves grammaticales avec traits, sans modifier le runtime

**Branche :** `research/verbnet-left-to-right-poc`
**Exécutions vérifiées :** [premier témoin borné](https://github.com/leye0/seman2/actions/runs/38924132290) et [unification incrémentale](https://github.com/leye0/seman2/actions/runs/38925068048).
**Rapports :** [oracle CFG](grammar_upper_bound.json), [témoins avec traits](feature_witness_report.json), [phrases longues](long_stress_report.json).

## Question vérifiée

La reconnaissance CFG sans traits acceptait les huit longues phrases du corpus de stress. Il fallait distinguer cette possibilité catégorielle de la présence d'une **dérivation concrète compatible avec les traits morphosyntaxiques**.

`feature_witness.py` est un instrument **hors ligne**, séparé du lecteur gauche-droite. Il :
1. récupère les spans productifs de l'oracle Earley sans traits ;
2. reconstruit de manière bornée des candidats à l'intérieur de ces spans ;
3. utilise **exactement** `PredictiveParser._reduce`, y compris `unify` et la preuve positive `requires` ;
4. applique facultativement le `ConstructionGuard` existant sur un arbre complet ;
5. renvoie `FOUND` uniquement avec un arbre concret. Une limite ou une recherche incomplète renvoie `UNKNOWN`, jamais « agrammatical ».

La seconde version ajoute unification partielle *avant* la combinaison complète et déduplication des lectures lexicales grammaticalement identiques. Les tests isolés vérifient l'accord, l'ambiguïté lexicale, les contraintes et les budgets.

## Résultat mesuré sur 8 phrases de 31–65 mots

| Mesure | Résultat |
| --- | ---: |
| Reconnaissance CFG permissive | 8/8 |
| Témoins feature-unified confirmés | **0/8** |
| Inconnus par limite de recherche | **8/8** |
| Budget maximum de reconstruction | 100 000 opérations par phrase |
| Unifications complètes tentées | 495–1 888 par phrase |
| Rejets précoces par traits | 11 225–37 001 par phrase |
| Temps de reconstruction supplémentaire | ~224–325 ms par phrase |
| Lectures lexicales identiques sautées | 0 |

Ces nombres concernent le **diagnostic hors ligne**, pas la latence du parseur. Le code de lecture de production et ses paramètres par défaut n'ont pas été modifiés.

## Verdict

**Aucun témoin positif n'est encore trouvé pour les longues phrases.** On ne peut donc pas attribuer les huit échecs à la seule stratégie gloutonne du lecteur : toutes les dérivations catégorie-compatibles pourraient être impossibles après unification, ou valides mais non atteintes sous nos budgets. Les résultats ne permettent pas de trancher.

La déduplication lexicale n'a pas eu d'effet sur ces huit phrases. L'unification incrémentale élimine de nombreux chemins mais une recherche top-down, même guidée par les spans, reste trop combinatoire. Continuer à accroître arbitrairement les budgets serait peu informatif.

## Expérience suivante justifiée

Construire **des backpointers de dérivations dans l'oracle Earley**, puis extraire un très petit nombre de **preuves structurelles complètes** guidées par le but et le contexte grammatical. Vérifier chacune par l'unificateur, avec statut `UNKNOWN` si les preuves sont épuisées ou coupées par budget. Avant de passer aux 8 longues phrases, valider cette extraction sur de courtes phrases réelles connues comme correctement analysées par Seman2, sans ajuster les règles depuis les exemples de stress ou le holdout.

Ce travail doit rester un **outil de recherche**, distinct de toute décision de production. Un arbre avec traits unifiables n'est pas nécessairement un arbre syntaxiquement correct : les assertions positives, les 24 négatives et le corpus indépendant English-EWT restent obligatoires avant toute promotion du lecteur.
