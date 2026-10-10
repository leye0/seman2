# Benchmark complet — *The Map of Everything*

Date : 2026-10-10

## Objet

Mesurer le moteur vectoriel avec segmentation hiérarchique précoce sur toutes
les phrases extraites de `data/the_map_of_everything_nlp_novel.txt`.

## Protocole

- 3 326 phrases produites par `extract_sentences`.
- Une seule instance de `Parser`, avec WordNet préchauffé avant la mesure.
- Analyse séquentielle de toutes les phrases.
- Plafond dur de 1 seconde par phrase. Un timeout interrompt uniquement la
  phrase courante ; la campagne continue avec la suivante.
- Les temps ci-dessous concernent les 2 712 phrases ayant rendu un résultat
  avant le plafond, qu'il soit complet ou incomplet.
- `recognition_ms` inclut la somme des reconnaissances locales et de
  l'assemblage lorsqu'une segmentation hiérarchique est retenue.
- `best_ms` mesure l'extraction nécessaire à la meilleure analyse rendue.

## Résultats globaux

| Mesure | Résultat |
|---|---:|
| Phrases visitées | 3 326 |
| Analyses complètes | 2 663 |
| Analyses incomplètes rendues | 49 |
| Timeouts à 1 s | 614 |
| Exceptions | 0 |
| Couverture sur le livre entier | **80,07 %** |
| Couverture hors timeouts | **98,19 %** |
| Segmentations hiérarchiques retenues | 200 |
| Hypothèses de segmentation rejetées avec repli global | 276 |
| Durée totale | 1 096,1 s (18 min 16 s) |

Le taux de 80,07 % traite volontairement chaque timeout comme un échec. Il ne
doit donc pas être confondu avec la seule couverture grammaticale : parmi les
phrases pour lesquelles le moteur a terminé, 98,19 % ont une analyse complète.

## Distribution des temps

| Mesure | Médiane | p90 | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|---:|
| Temps mural | 80,364 ms | 479,701 ms | 642,906 ms | 819,848 ms | 962,892 ms |
| Lexical | 1,823 ms | 3,800 ms | 4,561 ms | 6,409 ms | 347,868 ms |
| Reconnaissance | 44,197 ms | 255,714 ms | 566,829 ms | 699,636 ms | 817,259 ms |
| Extraction best | 18,379 ms | 69,926 ms | 119,429 ms | 525,294 ms | 873,531 ms |

La phrase pathologique qui a motivé la segmentation hiérarchique reste à
environ 59 ms à chaud, avec 158 combinaisons et 672 unifications. Son analyse
contient quatre propositions, trois relations `CONJUNCT` et la relation
`TEMPORAL` de `when`.

## Plus grands nombres de combinaisons terminés

| Index | Combinaisons | Temps | Phrase |
|---:|---:|---:|---|
| 2638 | 25 543 | 903,9 ms | The measurement notebook later helped volunteers calculate how much mulch they needed without ordering far too much. |
| 1019 | 24 248 | 831,4 ms | Ms. Rivera invited the children to write an optional description of a winter memory. |
| 3121 | 23 149 | 695,8 ms | Maya did not know how often they would write once school started. |
| 1335 | 22 571 | 786,6 ms | It was longer in distance yet easier than climbing around the work area. |
| 595 | 20 883 | 768,7 ms | She learned to think about patterns and habits instead of one frightening event. |
| 1172 | 19 918 | 784,7 ms | Maya had confused the price and surprise of a gift with how useful or welcome it would be. |
| 3116 | 19 817 | 684,1 ms | Maya had imagined Ben sitting alone and waiting for her letters. |
| 2086 | 19 270 | 655,3 ms | Grandma came over to bake bread rolls with Maya and Eli. |
| 400 | 19 253 | 568,9 ms | Mrs. Alvarez showed them the old gate but did not open it. |
| 497 | 18 701 | 629,9 ms | The different methods did not prevent the children from enjoying the same event. |

## Plus grands nombres d'unifications terminés

| Index | Unifications | Temps | Phrase |
|---:|---:|---:|---|
| 2638 | 38 460 | 903,9 ms | The measurement notebook later helped volunteers calculate how much mulch they needed without ordering far too much. |
| 1511 / 2193 / 3142 | 36 678 | 917–963 ms | Maya tried giving the same explanation to three imagined listeners: a younger child, a friend her age, and an adult who knew more than she did. |
| 1019 | 32 831 | 831,4 ms | Ms. Rivera invited the children to write an optional description of a winter memory. |
| 1335 | 32 509 | 786,6 ms | It was longer in distance yet easier than climbing around the work area. |
| 1172 | 31 588 | 784,7 ms | Maya had confused the price and surprise of a gift with how useful or welcome it would be. |
| 595 | 31 166 | 768,7 ms | She learned to think about patterns and habits instead of one frightening event. |
| 3121 | 28 935 | 695,8 ms | Maya did not know how often they would write once school started. |

## Exemples de timeouts

Les 614 timeouts ne se limitent pas aux longues listes coordonnées. Quelques
formes représentatives :

- `A place could stay the same while everything about a person's experience of it changed.`
- `They argued, changed their minds, asked questions, and finally left an empty square in the middle for places they had not discovered.`
- `Maya wondered how often adults shortened explanations because they were in a hurry and how often a missing detail changed the meaning.`
- `A place has an address and a position, but it also has a meaning to the people who use it.`
- `The children needed a book about the history of the empty lot, but the shelf labeled HISTORY OF OUR TOWN did not contain the address.`
- `Maya tried giving the same explanation to three imagined listeners: a younger child, a friend her age, and an adult who knew more than she did.`
- `Knowledge grows through observation, conversation, memory, revision, and discovering the limits of what we know.`

## Lecture des résultats

1. La segmentation précoce résout bien le cas initial : elle évite la forêt
   globale et conserve les relations entre propositions.
2. Elle est prudente : 276 propositions de découpage ont échoué leur validation
   locale ou leur assemblage et ont conservé le chemin global.
3. Le moteur est stable sur la totalité du corpus : aucune exception et une
   médiane de 80 ms malgré les cas difficiles.
4. Le prochain goulot n'est pas uniquement la coordination entre plusieurs
   propositions. Beaucoup de timeouts concernent les complétives, relatives,
   infinitives, négations et coordinations internes à une proposition.
5. Les cas terminés à 20 000–25 000 combinaisons montrent que l'extracteur
   k-best peut encore explorer un grand voisinage avant son premier résultat.
   Le prochain travail devrait instrumenter les timeouts par segment et par
   règle, sans élargir immédiatement le framework de segmentation.

## Diagnostic des timeouts et optimisation unique

Une seconde passe complète a instrumenté l'état vivant du parseur au moment
de chaque timeout. Les compteurs supplémentaires expliquent le petit écart
entre les 614 timeouts de la passe initiale et les 606 de la passe de
diagnostic : les cas proches d'une seconde peuvent changer de côté selon la
charge de la machine.

### Phase active au moment du timeout

| Phase | Timeouts avant optimisation |
|---|---:|
| Lexical | 0 |
| Reconnaissance | 0 |
| Extraction best | **603** |
| Assemblage hiérarchique | 3 |

Pour les 603 timeouts d'extraction, les médianes étaient de 551 nœuds de
forêt, 17 531 états partiels et **24 401 combinaisons visitées**. La médiane
des rejets d'unification directs et des rejets utilisés par les bornes était
782. La reconnaissance et WordNet n'étaient donc pas le goulet dominant.

### Dix timeouts les plus chargés

Le classement utilise la somme des opérations de reconnaissance, des
combinaisons et des unifications observées à une seconde.

| Index | Nœuds | Partiels | Contextes | Combinaisons | Rejets d'unification | Début de la phrase |
|---:|---:|---:|---:|---:|---:|---|
| 2861 | 1 142 | 34 605 | 1 134 | 31 412 | 2 227 | A bend in the trail made them seem… |
| 827 | 1 269 | 38 125 | 1 850 | 28 723 | 2 825 | The adult animal-service worker also reminded them… |
| 1312 | 1 580 | 48 420 | 386 | 20 765 | 1 367 | Maya understood that a person's illness… |
| 3039 | 1 458 | 48 542 | 245 | 19 150 | 1 637 | When the weather cleared and the adults confirmed… |
| 1955 | 1 689 | 48 311 | 122 | 20 952 | 1 376 | That evening, she reread several entries… |
| 1822 | 1 587 | 48 413 | 443 | 19 433 | 1 592 | Theo expected every pond animal… |
| 2796 | 874 | 28 222 | 1 296 | 30 733 | 1 383 | The numbers were useful, but Mom reminded them… |
| 1761 | 1 433 | 48 567 | 38 | 22 949 | 586 | In her notebook, she drew arrows… |
| 332 | 1 333 | 43 890 | 341 | 20 787 | Maya wrote in it on the bus… |
| 1287 | 1 262 | 40 043 | 701 | 23 163 | Her last sentence was a question… |

### Anomalie commune

Lorsqu'un enfant tardif d'une règle était épuisé sous un contexte de traits
et de bindings donné, l'extracteur essayait de nouveau ce même sous-problème
impossible pour chaque variante des enfants précédents. Ces variantes avaient
souvent la même interface grammaticale et ne pouvaient donc pas rendre le
suffixe compatible.

Sur des cas courts représentatifs, ce mécanisme produisait 6 000 à 13 000
analyses intermédiaires pour un seul nœud nominal. Les mêmes échecs étaient
réouverts des dizaines de milliers de fois, malgré une forêt relativement
petite.

### Optimisation appliquée

Une continuation enfant réellement épuisée est désormais mémorisée par :

```text
(règle, position RHS, nœud enfant, contraintes, bindings)
```

Une visite ultérieure du même sous-problème ne régénère plus ses voisins. Un
`None` dû à un cycle actif temporaire n'est jamais mémorisé : seuls les flux
marqués `exhausted` le sont. Cette optimisation ne modifie ni les scores, ni
K, ni les règles, et ne supprime aucune combinaison susceptible de réussir
dans un autre contexte grammatical.

Les 21 tests ciblés du moteur vectoriel et de couverture passent après ce
changement.

## Benchmark complet après optimisation

Le corpus a été rejoué avec exactement le même plafond d'une seconde et les
mêmes compteurs de diagnostic.

| Mesure | Diagnostic avant | Après optimisation | Évolution |
|---|---:|---:|---:|
| Analyses complètes | 2 670 | **3 078** | +408 |
| Analyses incomplètes rendues | 50 | 125 | +75 |
| Timeouts | 606 | **123** | **−79,7 %** |
| Exceptions | 0 | 0 | stable |
| Couverture brute | 80,28 % | **92,54 %** | +12,26 points |
| Durée totale | 1 080,6 s | **709,6 s** | **−34,3 %** |

Les 123 timeouts restants se répartissent ainsi :

| Phase | Nombre |
|---|---:|
| Lexical | 0 |
| Reconnaissance | 2 |
| Extraction best | 121 |
| Assemblage hiérarchique | 0 |

La médiane des phrases ayant rendu un résultat est de 89,5 ms, avec p90 à
578,5 ms, p95 à 694,7 ms et p99 à 894,5 ms. Le compteur rapporte **493 075
réutilisations de continuations impossibles** sur les phrases terminées.

Pour les timeouts d'extraction restants, la médiane tombe de 24 401 à 9 965
combinaisons. Ce groupe résiduel est différent et plus difficile : sa médiane
est de 908 nœuds et 30 369 partiels. Il ne faut donc pas généraliser la même
optimisation une seconde fois sans un nouveau diagnostic ciblé.

## Mutualisation des contextes grammaticaux projetés

Le diagnostic de cinq timeouts résiduels a révélé que la clé de cache d'un
sous-problème enfant contenait tous les bindings hérités du parent. Or, en
moyenne, seuls 0,35 à 0,54 binding étaient accessibles depuis l'interface de
l'enfant, contre 2,12 à 5,97 bindings présents dans la clé. Une même question
grammaticale était ainsi recalculée sous de nombreux chemins qui ne différaient
que par des variables sans rapport avec l'enfant. Selon la phrase, 67,4 % à
72,0 % des contextes observés étaient redondants après projection.

L'extracteur projette maintenant les bindings sur la fermeture des variables
réellement accessibles depuis la contrainte de l'enfant avant de consulter ses
caches. Les bindings étrangers sont rattachés au résultat retourné, de sorte
que les frères suivants conservent leur contexte et que les dérivations ainsi
que les interprétations distinctes restent disponibles. La même projection est
utilisée pour le cache des continuations impossibles. Aucun score, règle, K ou
mécanisme de segmentation n'a changé.

### Cinq phrases difficiles

Les nombres « avant » des quatre timeouts sont les compteurs atteints à une
seconde sans première analyse : leurs réductions sont donc des bornes basses.
La colonne d'unification donne `réussies / rejetées` pour les unifications
directes de l'extracteur.

| Index | Reconnaissance avant → après | Best avant → après | Combinaisons avant → après | Unifications avant → après | Résultat après |
|---:|---:|---:|---:|---:|---|
| 916 | 225,9 → 227,5 ms | >1 000 → 778,6 ms | ≥6 991 → 5 481 | 27 555/2 657 → 16 794/1 390 | 2 analyses demandées, score 72,17 |
| 3261 | 509,8 → 230,6 ms | >1 000 → 717,3 ms | ≥9 694 → 8 955 | 37 818/3 936 → 25 422/2 610 | 2 analyses, score 60,65 |
| 2823 | 558,7 → 587,7 ms | >1 000 → 148,5 ms | ≥15 652 → 640 | 38 546/2 198 → 3 212/344 | 2 analyses, score 70,70 |
| 2051 | 581,3 → 586,8 ms | 178,1 → 164,8 ms | 1 020 → 673 | 5 944/902 → 3 813/417 | 2 analyses, score 77,50 |
| 2903 | 456,4 → 168,8 ms | >1 000 → 281,9 ms | ≥6 522 → 2 970 | 15 669/788 → 9 866/743 | 2 analyses, score 55,25 |

Au moins **21 160 combinaisons** ont disparu sur ces cinq cas avant même de
tenir compte du travail que les quatre anciennes exécutions auraient poursuivi
au-delà d'une seconde. La demande d'une deuxième analyse n'a ajouté que 1,1 à
2,8 ms, ce qui confirme que les ambiguïtés n'ont pas été écrasées par la
mutualisation.

### Benchmark complet final

Le corpus de 3 326 phrases a été rejoué avec le même protocole et le même
plafond d'une seconde.

| Mesure | Avant projection | Après projection | Évolution |
|---|---:|---:|---:|
| Analyses complètes | 3 078 | **3 281** | +203 |
| Analyses incomplètes rendues | 125 | **31** | −94 |
| Timeouts | 123 | **14** | **−88,6 %** |
| Timeouts d'extraction | 121 | **11** | −110 |
| Timeouts de reconnaissance | 2 | 3 | +1, cas proches du plafond |
| Exceptions | 0 | 0 | stable |
| Couverture brute | 92,54 % | **98,65 %** | +6,11 points |
| Durée totale | 709,6 s | **590,8 s** | −16,7 % |

Sur les phrases terminées, la médiane est de 92,0 ms, p90 de 547,0 ms, p95
de 686,8 ms et p99 de 874,7 ms. Le cache projeté a servi **230 418 fois**.
Les 14 timeouts finaux se répartissent en 11 extractions et 3 reconnaissances.
Les 42 tests ciblés du moteur vectoriel, des traits, de la couverture et de la
grammaire générique passent.

