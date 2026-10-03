# Verdict LEX-06

## Verdict

**ADAPTATEUR À DÉVELOPPER — RESSOURCE, MAPPINGS ET LOOKUP DIRECT DES AXIOMES
VALIDÉS.**

Le dépôt SUMO installé contient les quatre fichiers de mappings WordNet 3.0
attendus et les ontologies SUO-KIF nécessaires. Aucun outil externe ne manque
pour lire ces données. Une intégration de production doit toutefois fournir un
adaptateur versionné : NLTK n'expose pas ces mappings et une recherche textuelle
naïve ne suffit pas pour préserver opérateurs, provenance et formules KIF.

La POC implémente le noyau de cet adaptateur : jointure par partie du discours
et offset WordNet, décodage des opérateurs, index de symboles KIF hors chaînes
de caractères, découpage des formules top-level équilibrées et restitution des
axiomes sources. Elle ne constitue ni un parseur SUO-KIF complet ni un moteur
de preuve.

## Inventaire observé

WordNet 3.0 installé contient 117 659 synsets. Les fichiers SUMO contiennent :

- 117 714 lignes de données, correspondant à 117 658 clés distinctes ;
- 56 lignes dupliquées dans le fichier nominal ;
- 115 951 clés portant au moins un mapping ;
- 1 707 clés présentes sans mapping SUMO ;
- 116 271 arêtes de mapping distinctes vers 5 465 concepts SUMO.

Les opérateurs des arêtes distinctes se répartissent ainsi :

- 99 203 mappings `+`, où le synset est subsumé par le concept ;
- 6 172 mappings `=`, déclarés équivalents ;
- 10 332 mappings `@`, où le synset dénote une instance du concept ;
- 8 compléments d'équivalence `:` ;
- 556 compléments de subsomption `[` ;
- aucun complément d'instance `]` dans cet instantané.

Les fichiers KIF de production sont limités aux 68 fichiers `*.kif` à la
racine du dépôt. Les répertoires `development/`, `tests/`, les traductions et
les artefacts générés sont exclus. Ce périmètre contient 189 087 formules
top-level et 40 483 symboles non cités distincts.

## Couverture et résolution

117 658 des 117 659 synsets WordNet ont une entrée, soit 99,9992 %. Le seul
synset absent est `curdle.v.03`. Si l'on exige un mapping effectif, la couverture
est de 115 951 synsets, soit 98,55 %.

115 754 des 116 271 arêtes de mapping, soit 99,56 %, pointent vers un symbole
trouvé dans les KIF de production. Les arêtes restantes ne sont pas supprimées :
101 noms de concepts distincts restent absents de ce périmètre. La liste
complète est conservée dans `corpus-inventory.json`; elle inclut notamment des
termes historiques, spécialisés ou manifestement irréguliers.

La différence entre lignes brutes et clés distinctes est réelle : 28 synsets
nominaux liés au papier et aux pages apparaissent chacun trois fois, produisant
56 doublons supplémentaires. L'adaptateur déduplique par clé WordNet et arête,
tout en conservant chaque numéro de ligne source.

## Exemples en langage humain

### Équivalence : `dog.n.01 → DomesticDog=`

Le synset `dog.n.01` est déclaré équivalent à `DomesticDog`. Le lookup KIF
retrouve treize formules, notamment :

- `DomesticDog` est une sous-classe de `DomesticAnimal` ;
- `DomesticDog` est une sous-classe de `Canine` ;
- `Puppy`, `Poodle`, `Sheepdog` et `Dachshund` sont des sous-classes de
  `DomesticDog` ;
- une documentation définit les chiens domestiques comme issus du loup commun
  par élevage sélectif ;
- une règle concernant `DogBowl` et plusieurs formats ou images externes.

L'opérateur `=` est une assertion du fichier de mapping SUMO. La POC la
conserve comme relation attribuée ; elle ne fusionne pas les identifiants
WordNet et SUMO dans le graphe cognitif.

### Subsomption : `choke.v.01 → Breathing+`

`choke.v.01`, « respirer avec grande difficulté », est plus étroit que le
concept SUMO `Breathing`. L'opérateur `+` signifie que le synset est subsumé
par ce concept, et non qu'il lui est équivalent.

Quarante-six formules mentionnent `Breathing`. Les relations directes le
placent sous `OrganismProcess` et `AutonomicProcess`. D'autres axiomes relient
la respiration à des organismes, appareils médicaux et processus
biochimiques. La POC restitue ces formules, mais ne déduit pas automatiquement
que toute propriété de `Breathing` s'applique à chaque occurrence de
`choke.v.01`.

### Instance : `hegira.n.01 → Escaping@`

Le synset désignant l'Hégire est mappé avec `@` vers `Escaping`. Cela signifie
que le synset dénote une instance de la classe SUMO `Escaping`, pas qu'il est
une sous-classe de celle-ci.

Le KIF affirme directement que `Escaping` est une sous-classe de
`Translocation`, fournit sa documentation et quatre règles sur la relation à
un confinement antérieur. Ces règles restent des axiomes externes accessibles,
sans exécution par la POC.

### Deux formes d'absence sont distinguées

`acroscopic.a.01` possède une ligne dans `WordNetMappings30-adj.txt`, mais
aucune annotation `&%Concept opérateur`. Son statut est
`present_without_sumo_mapping`.

`curdle.v.03` existe dans WordNet 3.0 mais n'a aucune ligne dans le fichier
verbal. Son statut est `absent_from_mapping_files`. Ces deux situations ne sont
pas confondues et aucun concept de remplacement n'est inventé.

## Frontière entre lookup et inférence

Le chemin validé comporte trois opérations distinctes :

1. une analyse déjà associée à un synset WordNet fournit sa partie du discours
   et son offset ;
2. le fichier WordNet–SUMO retourne zéro ou plusieurs arêtes typées ;
3. le nom du concept permet de retrouver les formules KIF qui le mentionnent.

La première étape suppose que le sens WordNet a déjà été choisi. Cette POC ne
fait aucune désambiguïsation lexicale. La troisième étape est un index direct,
pas une fermeture logique : les superclasses transitives, conséquences de
règles, satisfiabilité et preuves ne sont pas calculées.

## Rapport à l'architecture

SUMO doit rester une ressource ontologique externe attribuée. Une analyse peut
porter un lien vers un concept SUMO, l'opérateur du mapping, les axiomes
sources, leur fichier, leur ligne et la révision du dépôt. Elle ne doit pas
transformer automatiquement :

- une équivalence de mapping en identité interne irréversible ;
- une subsomption en assertion directe de toutes les propriétés du concept ;
- un mapping d'instance en déclaration de classe ;
- une absence de mapping en preuve d'absence conceptuelle.

Pour aller au-delà du lookup, un composant séparé devra choisir un parseur et
un raisonneur SUO-KIF, définir le périmètre des ontologies chargées et attribuer
toute conclusion dérivée aux axiomes et à la version utilisées. SigmaKEE peut
être ajouté pour la navigation ou l'édition, mais n'est pas requis pour
l'adaptateur de données démontré ici.

## Limites

- La POC utilise WordNet 3.0 et la révision SUMO
  `77f8fdd2a6e8970c68e452cecb051aaa441c0387`.
- Le lecteur KIF reconnaît les formules top-level équilibrées, commentaires de
  ligne et chaînes échappées. Il ne prétend pas couvrir toute extension
  possible de SUO-KIF.
- L'index exige une correspondance exacte du symbole hors chaîne de caractères.
- Seuls les KIF de production à la racine sont indexés ; les ontologies de
  développement et les données générées sont volontairement hors périmètre.
- Les mappings négatifs sont conservés comme relations distinctes, sans
  interprétation logique supplémentaire.
- Aucun raisonnement, aucune désambiguïsation de sens et aucune modification de
  l'ontologie ne sont effectués.
