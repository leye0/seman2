# POC du moteur prédictif incrémental

## Verdict

La POC démontre que l'ordre statistique des actions est très efficace sur les
constructions ordinaires, mais **elle n'est pas prête à remplacer le moteur de
production**. Sur les 50 premières phrases, le modèle entraîné atteint 100 % de
couverture avec un p50 de 6,12 ms, contre 9,80 ms pour le moteur actuel. Sur les
300 phrases, les longues coordinations, chaînes de PP et enchâssements font
encore exploser les reprises : couverture 90,67 %, p50 17,48 ms et p95
2 176 ms. Aucun échec n'est masqué par un fallback.

Le résultat utile est donc double : le fast path est réel sur le sous-ensemble
simple/ordinaire, et le shift/reduce à pile unique n'est pas une architecture
suffisante pour les régions complexes sans une représentation partagée locale.

## Architecture effectivement testée

`PredictiveGrammar` compile les 385 règles en identifiants de catégories,
index exacts de RHS et listes d'arités par dernière catégorie. Une réduction
fait au plus une recherche par arité compatible; elle ne parcourt jamais les
385 règles. `PredictiveParser` lit le lattice de gauche à droite, classe les
SHIFT/REDUCE autorisés, conserve les autres comme points de reprise et s'arrête
au premier `CLAUSE` couvrant l'entrée.

Les nœuds restent compacts pendant la recherche. Le `ChartItem` et son paquet
syntaxique ne sont matérialisés qu'après acceptation. Chaque réduction applique
l'unification, les traits `requires`, la propagation de preuves de traits et la
substitution du LHS. Le modèle ne peut donc jamais autoriser une action refusée
par la grammaire.

La faisabilité LR(0), mesurée sur la grammaire sans même ajouter les traits,
donne :

| mesure | valeur |
|---|---:|
| règles | 385 |
| états LR(0) | 730 |
| items d'état | 124 973 |
| transitions | 13 074 |
| états conflictuels | 402 |
| paires shift/reduce | 16 892 |
| paires reduce/reduce | 842 |
| règles récursives à gauche | 78 |
| index left-corner estimé | 66 984 octets |

Ces conflits, avant les traits, justifient le choix left-corner sélectif plutôt
qu'un LR/LALR déterministe forcé.

## Modèle statistique

`TransitionModel` persiste quatre niveaux interpolés : fréquence globale,
sommet de pile, sommet + prochain POS, puis trois catégories de pile + prochain
POS. Le lissage est :

```text
P(a|c) = (count(c,a) + alpha * P(a|parent(c))) / (count(c) + alpha)
```

Un backoff supplémentaire sur la classe SHIFT/REDUCE protège les règles rares.
Les lexèmes exacts ne figurent pas dans les contextes. Le fichier entraîné
contient 225 arbres exacts après normalisation avec poids 1,0 et 75 dérivations
syntaxiquement valides mais non exactes marquées *silver* avec poids 0,25. Ce
dernier poids est explicite et contrôlable; il ne s'agit pas d'apprentissage en
ligne auto-confirmant. Le modèle se régénère avec :

```bash
cd superparser
python scripts/train_predictive.py
```

Le corpus de 300 phrases sert ici à l'amorçage et au développement. Les chiffres
sur ce même corpus ne prouvent donc pas la généralisation.

## Mesures

Commande :

```bash
cd superparser
python scripts/bench_predictive.py --output predictive_benchmark.json
python scripts/bench_predictive.py --limit 50 --max-states 5000 \
  --include-untrained --output predictive_ablation_50.json
```

Résultats à chaud sur les 300 phrases :

| moteur | couverture | exact normalisé (diagnostic) | p50 | p95 | p99 | max | total |
|---|---:|---:|---:|---:|---:|---:|---:|
| production vector | 100 % | 75,0 % | 14,08 ms | 84,69 ms | 377,71 ms | 454,12 ms | 8 975 ms |
| prédictif entraîné | 90,67 % | 52,33 % | 17,48 ms | 2 176 ms | 2 884 ms | 3 700 ms | 86 222 ms |

Dans deux interpréteurs frais (cache disque du système non contrôlé), la
construction + première analyse de `The child laughed.` mesure 2 945 ms pour la
production et 2 913 ms pour le prédictif. Environ 2,9 s viennent du premier
accès lexical/WordNet; ce coût froid ne doit pas être confondu avec le parsing à
chaud ni avec la compilation de l'index prédictif.

Le prédictif crée 1 019 057 états, exécute 1 018 757 transitions et effectue
753 823 reprises sur l'ensemble complet. Le pic `tracemalloc`, mesuré dans une
passe séparée sur les dix premières phrases, est de 232 401 octets contre
875 907 pour le moteur vectoriel. La matérialisation prédictive est peu coûteuse
(p50 0,13 ms); le problème restant est sans ambiguïté la recherche.

Sur les 50 premières phrases :

| variante | couverture | p50 | p95 | transitions | reprises |
|---|---:|---:|---:|---:|---:|
| production | 100 % | 9,80 ms | 37,96 ms | 66 551 | n/a |
| prédictif entraîné | 100 % | 6,12 ms | 26,01 ms | 3 993 | 1 653 |
| prédictif non entraîné | 98 % | 6,87 ms | 145,34 ms | 26 446 | 17 858 |

L'entraînement réduit donc fortement la queue et le travail, mais il ne résout
pas la croissance combinatoire des structures complexes.

## Ambiguïtés et expansion

En mode FAST, chaque conflit rencontré sur le chemin gagnant devient un
`AmbiguityPoint`; le résultat annonce explicitement que l'exploration n'est pas
exhaustive. `expand(result, ambiguity_id)` repart du checkpoint compact associé
et réutilise le lattice lexical.

Pour `I saw the man with a telescope.`, FAST choisit d'abord :

```text
NP [the man [PP with a telescope]]
```

Le checkpoint situé avant `with` conserve aussi `reduce:vp_transitive`.
L'expansion de ce point produit :

```text
VP [[saw the man] [PP with a telescope]]
```

Les sous-arbres lexicaux sont reconstruits à la matérialisation, mais le préfixe
de recherche et le lattice ne sont pas reparcourus. L'API représente aujourd'hui
les choix par actions/règles; une future couche sémantique pourra les projeter en
relations d'attachement.

## Limites observées et intégration recommandée

Les échecs se concentrent dans les doubles PP, coordinations de propositions et
longs enchâssements. La pile linéaire du prototype doit reprendre trop loin
lorsqu'une réduction locale ferme la mauvaise région. Augmenter seulement le
budget finit par retrouver certaines analyses, mais reproduit le retour arrière
massif que le projet veut éliminer.

Recommandation : ne pas brancher cette POC dans le runtime de production.
Conserver le compilateur, le modèle persistant, les contextes et l'API
FAST/EXPAND, puis remplacer la pile unique par un **GLR local partagé uniquement
aux conflits**. Les états déterministes doivent rester sur le chemin rapide;
une petite GSS/SPPF doit s'ouvrir lors d'un conflit non résolu et se refermer
dès convergence. Cela réutilisera les bons résultats mesurés (index compact,
filtrage lexical, 0,13 ms de matérialisation, avantage net sur les phrases
ordinaires) sans accepter la queue catastrophique actuelle.

Les résultats complets et les listes d'échecs sont dans
`predictive_benchmark.json`; l'ablation entraîné/non entraîné est dans
`predictive_ablation_50.json`.
