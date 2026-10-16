# Itérations : points de réduction, observations du parent et garde de conformité

**Branche :** `research/verbnet-left-to-right-poc`  
**Exécution validée :** [GitHub Actions #38894920360](https://github.com/leye0/seman2/actions/runs/38894920360)  
**Rapports :** [grammaire positive / négative](grammar_quality_gate.json) · [phrases longues](long_stress_report.json) · [English EWT](ud_ewt_probe.json).

## Problème étudié

Le lecteur Left-to-Right sait conserver un petit nombre de points de reprise, mais
jusqu'ici il ne pouvait essentiellement choisir que **quel symbole grammatical
consommer**. Un deuxième conflit existe dans la grammaire elle-même : une suite
`VP -> V` est déjà grammaticalement complète, alors qu'une règle
`VP -> V NP` peut la prolonger. Si le parent attend aussi `NP`, consommer
le mot dans le `VP` peut priver le parent de son complément.

Trois stratégies nouvelles ont été testées sans modifier `grammar.jsonl` :

1. **Réduction différée libre** : mémoriser une option `$REDUCE` dès que
   l'état a des règles finales compatibles, puis y revenir si le chemin
   de continuation échoue.
2. **Réduction immédiate sur indice du parent** : lorsque le parent attend
   explicitement un symbole compatible avec le prochain token, préférer
   réduire l'enfant, tout en permettant une restauration.
3. **Réduction différée restreinte** : n'autoriser une reprise
   `$REDUCE` que si le parent fournit cet indice positif de FOLLOW.

Dans les trois cas, les décisions de réduction ne sont pas des règles
lexicales inventées; elles utilisent le même trie grammatical compilé et
les mêmes unifications. Le budget reste **une ou trois restaurations**
maximum, avec **un seul arbre actif**; les snapshots partagent leurs
enfants immuables, sans forêt de dérivations.

## Dernière ablation complète (120 positives annotées, 24 négatives)

| Mode | Assertions positives satisfaites / 120 | Négatives acceptées / 24 | Médiane totale |
| --- | ---: | ---: | ---: |
| A, baseline | 34 | 6 | 3,40 ms |
| AI, promotion unaires + garde + 1 reprise | 41 | **1** | **4,85 ms** |
| AK, réduction différée libre + 1 reprise | **44** | **1** | 5,08 ms |
| AL, réduction différée libre + 3 reprises | **53** | 2 | 5,58 ms |
| AM, réduction immédiate parent + 1 reprise | 39 | 1 | 4,97 ms |
| AN, réduction immédiate parent + 3 reprises | 52 | 2 | 5,55 ms |
| AO, réduction restreinte par FOLLOW + 1 reprise | **44** | **1** | 5,08 ms |
| AP, réduction restreinte par FOLLOW + 3 reprises | **49** | **1** | 5,64 ms |

**Interprétation :**
- **AI** est le compromis strictement sous 5 ms de cette exécution.
- **AK / AO** améliorent le résultat à **44** sans nouvelle fausse
  acceptation ni régression sur les annotations positives, mais la médiane
  mesurée est légèrement supérieure à 5 ms et varie avec la machine.
- **AL** a le meilleur total positif (**53**), mais accepte aussi
  `She depends of her friends.` via
  `vp_intransitive + vp_pp`. Ce cas demande une vraie modélisation de la
  valence prépositionnelle, **pas** un blocage de mot spécifique.
- **AM / AN** font **régresser** des cas positifs autrefois corrects :
  une simple preuve FIRST/FOLLOW est trop faible pour forcer la réduction.
- **AP** garde la seule fausse acceptation connue du garde de référence,
  améliore les assertions à **49**, mais n'atteint pas 5 ms de médiane.
- Les 120 vérifications restent des **assertions partielles**, et non un
  contrôle exhaustif des arbres par dépendances étiquetées.

## Résultats par split : lecture sans surajuster le holdout

| Mode | Dev / 50 | Validation / 50 | Holdout / 20 |
| --- | ---: | ---: | ---: |
| A | 12 | 16 | 6 |
| AI | 15 | 19 | 7 |
| AK | 16 | 20 | 8 |
| AP | 19 | 22 | 8 |
| AL (ne passe pas le garde négatif) | 21 | 24 | 8 |

L'ensemble holdout sert uniquement à vérifier, jamais à ajuster la
grammaire ni les scores des exemples.

## Phrases longues et corpus externe : toujours insuffisant

- **8 phrases longues stress (31–65 mots) : 0/8 terminées**, pour toutes
  les variantes. Les réductions différées permettent parfois d'atteindre
  plus de tokens, jusqu'à 92 % sur un exemple, mais **une progression
  partielle rapide n'est pas un parsing réussi**.
- **English EWT, 32 phrases externes (8–70 mots) : 1/32** avec les
  meilleures variantes exploratoires; aucun alignement complet des feuilles
  syntaxiques aux annotations POS n'a permis de valider un arbre.
- Le coût médian des longues phrases reste de l'ordre de **19 ms** pour les
  variantes à trois reprises. Ce n'est pas une cible satisfaite.

## Décision et prochain travail pertinent

**Aucun changement n'est activé par défaut dans le runtime de production.**
Les variantes restent disponibles dans la branche en tant qu'options A/B.
Recommandation provisoire : **AI** pour la médiane stricte, **AO/AK** pour
essayer plus de couverture sous une tolérance légère, **AP** pour la
recherche de qualité (pas GO pour une cible de 5 ms).

Le verrou principal n'est plus l'absence de points de reprise : il reste
la **couverture réelle des dépendances grammaticales et des clauses
enchâssées**, ainsi que la représentation de la valence sélectionnant une
préposition. Améliorer cela de façon générale et validable sur des arbres
réels est plus important que multiplier encore les chemins de recherche.

L'objectif reste une **médiane autour de 5 ms avec reconnaissance
grammaticalement conforme**, en suivant systématiquement le p95, les faux
positifs et la progression réelle sur les phrases longues.
