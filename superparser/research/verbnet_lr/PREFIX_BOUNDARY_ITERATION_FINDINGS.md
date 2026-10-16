# Itérations lexicales et frontières de constituants — 2026-10-16

**Branche :** `research/verbnet-left-to-right-poc`
**CI comparative réussie :** [GitHub Actions #38918831963](https://github.com/leye0/seman2/actions/runs/38918831963)
**Contrôles :** [conformité](grammar_quality_gate.json), [lecteur](reader_ablation.json), [négatifs](negative_report.json), [phrases longues](long_stress_report.json), [corpus UD EWT](ud_ewt_probe.json).

## Diagnostic à l'origine du changement

Les traces montrent des choix de catégories lexicales plausibles mais non
conformes à la continuation déjà compilée. Par exemple, dans `had already
examined`, `had` pouvait être lu comme `V` au lieu de `HAVE`, et le lecteur
cherchait un groupe nominal après ce faux verbe. Plusieurs arrêts précoces
sur les 8 phrases longues résultaient de décisions comparables.

Une autre ambiguïté oppose **étendre un constituant déjà complet** et le
**rendre à son appelant**. Le lecteur protégeait les séparateurs du parent
immédiat, mais ne conservait pas systématiquement l'alternative lorsque le
séparateur appartenait à un ancêtre plus éloigné.

## Modifications expérimentales, désactivées par défaut

1. **Preuve directe de préfixe sur trois tokens** : à concurrence de plusieurs
   transitions grammaticales, explorer au plus deux tokens futurs dans le
   trie compilé. On exige une suite lexicale directe et au moins une règle
   commune à chaque étape. Ne changer le choix que lorsqu'une *unique*
   transition dispose de cette preuve positive. Aucun arbre alternatif,
   aucune règle nouvelle, aucun recours au parseur de production.
2. **Reprises limitées par FOLLOW** : réutiliser le témoin grammatical du
   parent pour permettre une réduction différée. On évite ainsi
   d'autoriser une extension simplement par énumération de possibilités.
3. **Checkpoint de frontière d'extension** : si une extension grammaticale
   peut démarrer, mémoriser l'alternative `$FINISH` : terminer le
   constituant déjà construit et rendre la main au parent. Les
   restaurations restent bornées, sans forêt.
4. **Tests et diagnostics** : configurations identiques entre les 120 cas
   positifs et les 24 négatifs, suivi de la stabilité inter-répétitions et
   traces lexicales des 8 longues phrases.

## A/B mesurée (même exécution CI)

| Mode | Assertions satisfaites /120 | Négatives acceptées /24 | Médiane totale | p95 |
|---|---:|---:|---:|---:|
| AR — filtrage des snapshots, 3 reprises | 53 | 2 | 5,72 ms | 10,61 ms |
| AS — preuve 3 tokens, 1 reprise | 46 | 1 | 5,26 ms | 10,17 ms |
| AT — preuve 3 tokens, 3 reprises | 57 | 2 | 5,80 ms | 11,10 ms |
| AU — preuve + FOLLOW, 2 reprises | 51 | 1 | 5,78 ms | 10,44 ms |
| AV — preuve + FOLLOW, 3 reprises | 53 | 1 | 6,13 ms | 11,41 ms |
| AW — preuve + checkpoint d'extension, 3 reprises | **60** | 2 | 5,80 ms | 11,24 ms |
| AX — preuve + FOLLOW + extension, 3 reprises | **54** | **1** | 6,07 ms | 11,20 ms |
| AY — preuve + FOLLOW + extension, 2 reprises | 52 | 1 | 5,64 ms | 10,45 ms |

**Important :** 60/120 signifie que toutes les *assertions explicitement
annotées* sont satisfaites, pas que 60 arbres sont entièrement validés.
Les 24 phrases négatives sont un petit banc de discrimination, pas une
preuve de correction générale. La latence varie selon le runner :
le seuil de 5 ms n'est **pas** atteint pour ces modes sur ce run.

**Qualité :** le mode AX garde une seule fausse acceptation, `neg023`
(`She enjoys read.`), et n'en ajoute pas par rapport au mode AP ; AW
accepte aussi `neg024` (`She depends of her friends.`). Les
erreurs exigent des contraintes de valence/préposition et de sélection
complémentaire, pas des interdictions de chaînes spécifiques.

Les rapports incluent les contrôles de stabilité : les variantes ci-dessus
n'ont pas de variation du résultat grammatical entre les répétitions de cette
exécution.

## Phrases longues et généralisation externe

- **0/8** phrases stress longues complétées (31 à 65 mots) pour les modes
  comparés. La preuve de préfixe fait passer `stress_03` d'environ
  **11 % à 50–54 %** des tokens ; le checkpoint d'extension n'améliore
  pas régulièrement ces longueurs et peut même régresser sur certains cas.
- **1/32** phrases UD English EWT externes terminées par les variantes
  complexes. Une complétion n'est pas une évaluation exhaustive de l'arbre.
- Les échecs restants concernent notamment les relatives enchâssées,
  les lectures `WH-NOM`/pronom relatives, les propositions avec auxiliaires
  et la valence des compléments; pas une simple augmentation nécessaire
  du budget de reprises.

## Verdict et prochaines expériences

- **Ne rien activer par défaut** dans le parseur de production ni dans
  le lecteur de référence. Conserver les modes sous drapeau A/B.
- **AX** : meilleure qualité mesurée parmi les variantes de cette série
  avec au moins 54 conformités (54/120, 1/24), mais performance > 5 ms.
  **AW** : meilleure couverture brute (60/120) mais garde négatif échoué.
- Tester des choix de continuations **à support positif discriminant**,
  avec arrêt `INCOMPLETE` si les observations sont insuffisantes. Ne pas
  chercher à atteindre l'objectif en augmentant arbitrairement les
  relectures ou en ajoutant des règles ajustées aux 8 phrases stress.
- Priorité conjointe : optimisation du chemin de lecture et validation des
  sélections `VP-NP`/auxiliaires, relatives et prépositions sur corpus
  indépendant, avec p50, p95, faux positifs et stabilité sur chaque run.
