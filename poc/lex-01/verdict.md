# Verdict LEX-01

## Verdict

**GO COMME RESSOURCE DE CANDIDATS LEXICAUX.**

NLTK WordNet 3.0 fournit bien les structures exigées : synsets candidats,
identifiants versionnés, parties du discours, lemmes et clés de sens,
définitions, exemples, hyperonymes, hyponymes, méronymes, holonymes, antonymes
et relations dérivationnelles.

Il ne fournit pas, par un simple lookup, le sens d'une occurrence en contexte.
WordNet doit donc alimenter le système en hypothèses lexicales concurrentes,
jamais remplacer une occurrence par un synset supposé vrai.

## Couverture observée

| Fixture | Résultat |
|---|---:|
| `bank` — polysémie | 18 synsets candidats |
| `dogs` — flexion | 8 synsets ; formes de base nominale et verbale `dog` |
| `credit card` — composé | 0 avec l'espace, 1 avec la clé `credit_card` |
| `decision` — dérivation | 5 synsets, dont des liens vers `decide` |
| `car` — méronymie/holonymie | 5 synsets avec relations partie/tout |
| `good` — antonymie | 27 synsets, dont des liens lemma-à-lemma vers `bad` |
| `florpblatz` — absence | 0 synset, absence représentée explicitement |

Au total, la POC conserve 64 synsets candidats et 162 lemmes. Elle observe 43
liens hyperonymiques, 131 hyponymiques, 33 méronymiques, 9 holonymiques, 12
antonymiques et 89 dérivationnels. Cinquante-cinq synsets possèdent au moins un
exemple ; pour les autres, la liste vide est conservée au lieu d'inventer un
exemple.

## Exemples en langage humain

### `bank` : une liste de sens, pas une décision

WordNet renvoie notamment :

- `bank.n.01`, la pente ou rive située au bord d'un cours d'eau ;
- `depository_financial_institution.n.01`, l'institution qui reçoit des dépôts
  et prête de l'argent ;
- d'autres noms comme une levée de terre ou une réserve ;
- plusieurs emplois verbaux de `bank`.

Pour **“They sat on the bank of the river.”**, un humain privilégie la rive.
Pour **“They deposited the money at the bank.”**, il privilégie l'institution
financière. Le lookup WordNet reçoit pourtant seulement la chaîne `bank` et
renvoie exactement les mêmes 18 synsets dans les deux cas. Aucun candidat
n'est sélectionné.

La désambiguïsation devra donc utiliser séparément la syntaxe, les autres mots,
le discours et les connaissances actives. L'ordre de la liste WordNet ne doit
pas être interprété comme une décision contextuelle.

### `dogs` : récupération morphologique et polysémie persistante

Pour `dogs`, `morphy` retrouve `dog` comme nom et comme verbe. Le lookup renvoie
ensuite `dog.n.01`, l'animal domestique, mais aussi des emplois figurés et
techniques ainsi que `chase.v.01` pour le verbe « poursuivre ».

La réduction morphologique n'est donc pas une désambiguïsation : elle permet de
retrouver les entrées candidates, puis l'ambiguïté demeure.

### `credit card` : transformation nécessaire et traçable

`wn.synsets("credit card")` retourne zéro résultat. WordNet encode ce composé
sous la clé `credit_card`; cette clé retourne `credit_card.n.01`, avec les
lemmes `credit_card`, `charge_card`, `charge_plate` et `plastic`.

Le remplacement des espaces par des underscores est une opération de
l'adaptateur. La POC conserve la forme observée, la clé effective et le nom de
la transformation afin de ne pas présenter `credit_card` comme le texte reçu.

### `decision` : relations entre familles de mots

`decision.n.01` signifie l'acte de prendre une décision. Ses relations
dérivationnelles lemma-à-lemma conduisent notamment à `decide.v.01`. Les
sorties exposent aussi la clé de sens de chaque lemme source et cible : le lien
ne devient donc pas une simple association non attribuée entre deux chaînes.

### `car` : relations partie/tout typées

Pour l'automobile `car.n.01`, WordNet énumère des parties telles que le moteur,
les portes, les sièges, les fenêtres ou le coffre. Pour le sens ferroviaire
`car.n.02`, le wagon possède le train comme holonyme membre. Les types `part`,
`member` et `substance` restent séparés dans les résultats.

### `good` : les antonymes appartiennent aux lemmes

Les relations d'antonymie relient des lemmes précis, par exemple le lemme
`good` de `good.a.01` au lemme `bad` de `bad.a.01`. Elles ne doivent pas être
généralisées aveuglément à chacun des 27 synsets associés à la chaîne `good`.

### Terme absent

`florpblatz` ne possède ni forme de base reconnue ni synset. La source reste
présente avec `status = no_candidates`. L'absence dans WordNet ne signifie ni
que le texte doit être supprimé, ni que le concept ne peut pas être appris par
le système.

## Rapport à l'architecture

Chaque requête demeure une observation source distincte. Chaque synset est une
analyse externe dotée d'un identifiant stable, du producteur NLTK WordNet, de
la version de la ressource et d'un lien vers l'observation. Tous les candidats
coexistent et `selected_by_lookup` reste faux.

Les synsets, définitions et relations constituent des observations structurées
externes. Ils ne définissent pas directement l'ontologie du Learned Graph. Le
moteur peut les utiliser, les contredire ou apprendre d'autres regroupements.

Cette séparation est particulièrement importante pour les termes absents, les
composés normalisés et les mots fortement polysémiques : aucune opération de
lookup ne remplace le matériau observable original.

## Limites

- La POC utilise Princeton WordNet 3.0 en anglais.
- Les identifiants et offsets sont propres à cette version et doivent toujours
  être accompagnés de `resource_version`.
- Les relations enregistrées sont les relations immédiates renvoyées par NLTK,
  pas leur fermeture transitive.
- Les exemples sont ceux de la ressource et plusieurs synsets n'en possèdent
  pas.
- Le lookup de composé démontré utilise une normalisation explicite vers les
  underscores ; une segmentation générale des expressions multi-mots relève de
  l'adaptateur lexical et des analyses en amont.
- La sélection du bon sens pour une occurrence nouvelle appartient à
  l'alignement occurrence → ressources de LEX-07 et au moteur contextuel, pas à
  LEX-01.
