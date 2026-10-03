# Verdict LEX-04

## Verdict

**GO COMME RESSOURCE LEXICALE ET CORPUS ANNOTÉ, PAS COMME DÉTECTEUR DE
FRAMES.**

NLTK FrameNet donne accès aux définitions de frames, aux unités lexicales, aux
éléments de frame et à leur statut de coreness, aux core sets, aux types
sémantiques, aux relations entre frames et aux mappings entre leurs éléments.
Le lecteur charge aussi les exemples lexicographiques avec la cible et les
couches `FE`, `GF`, `PT`, ainsi que les instanciations nulles.

La valence est bien distribuée dans les fichiers `lu/*.xml`, sous forme de
`FERealization`, `FEGroupRealization`, `pattern`, `valenceUnit` et références
aux annotation sets. Elle n'est toutefois pas exposée par l'objet LU de NLTK
3.10.3 : son lecteur ignore explicitement l'élément `<valences>`. La POC ajoute
une lecture minimale du XML local, conserve cette provenance distincte et
vérifie que chaque exemple choisi est référencé par ses patterns de valence.

## Données observées

La ressource installée contient :

- 1 221 frames ;
- 13 572 unités lexicales ;
- 11 428 éléments de frame, dont 3 501 `Core`, 123 `Core-Unexpressed`, 2 781
  `Extra-Thematic` et 5 023 `Peripheral` ;
- 2 070 relations entre frames, dont 781 `Inheritance`, 556 `Using`, 217
  `ReFraming_Mapping`, 131 `Subframe` et 127 `Perspective_on` ;
- 202 403 exemples annotés selon les compteurs des unités lexicales ;
- 107 documents full-text dans les métadonnées NLTK.

Les quatre fixtures portent sur trois frames et trois unités lexicales. Elles
conservent quatre annotation sets, douze annotations d'éléments de frame et une
instanciation nulle. `Self_motion` illustre notamment une frame riche de 152
unités lexicales ; `Statement` en contient 79 et `Commerce_buy` six.

## Exemples en langage humain

### `Commerce_buy` relie inventaire, héritage et occurrence annotée

La frame `Commerce_buy` définit notamment `Buyer` et `Goods` comme éléments
`Core`, et `Money` et `Seller` comme éléments périphériques. Elle hérite de
`Getting` avec neuf mappings explicites entre éléments de frame. Elle est aussi
reliée par `Perspective_on` à `Commerce_goods-transfer`, et par d'autres
relations à `Renting`, `Importing` et `Shopping`.

Dans **“I bought an old Harmony Sovereign acoustic guitar for £20 from an
absolute prat”**, l'annotation existante cible `bought`. Les spans `Buyer`,
`Goods`, `Money` et `Seller` sont alignés respectivement avec les fonctions
grammaticales `Ext`, `Obj`, `Dep`, `Dep` et les types de syntagmes `NP`, `NP`,
`PP`, `PP`. Ces informations viennent des couches parallèles de l'annotation,
pas d'une nouvelle analyse effectuée par la POC.

### La valence représente aussi les arguments absents

Dans l'impératif **“Buy what is functional and decorative”**, `Goods` est
réalisé par la proposition interrogative, tandis que `Buyer` porte le code
`CNI` et n'a donc aucun span inventé. Le pattern de valence correspondant relie
explicitement son annotation set à cette réalisation constructionnelle nulle.

Pour `buy.v`, le XML contient dix réalisations individuelles réparties sur 29
patterns, et dix-sept réalisations de groupes réparties sur 48 patterns. Un
même annotation set peut légitimement apparaître dans plusieurs tables : la
POC conserve ces références plutôt que de les fusionner.

### `Self_motion` montre l'héritage multiple et les core sets

`Self_motion` possède 23 éléments et hérite notamment de `Motion` et
`Intentionally_act`. Ses relations d'héritage contiennent les mappings vers
les éléments des frames parentes ou filles. Son core set est conservé comme un
ensemble structuré, sans le réduire à une liste de labels indépendants.

Dans **“a ladybird ambling about on his twitching nose”**, la cible `ambling`
et les éléments `Self_mover`, `Area` et `Place` ont des charspans exacts, avec
leurs fonctions grammaticales et types de syntagmes correspondants.

### Les offsets sont normalisés sans perdre la convention native

FrameNet encode la borne finale d'un label comme inclusive. La sortie de la
POC la convertit en `end_exclusive` pour obtenir des spans Python demi-ouverts,
et documente cette conversion. Les labels sans span gardent `start` et
`end_exclusive` à `null`, accompagnés de leur type d'instanciation nulle.

## Frontière entre ressource et détection automatique

Trois opérations doivent rester distinctes :

1. un lookup de frame restitue une définition et un réseau lexical stockés ;
2. un lookup d'un exemple restitue une annotation humaine déjà présente dans
   FrameNet ;
3. l'analyse d'une phrase nouvelle devrait identifier une cible, désambiguïser
   sa frame et étiqueter les éléments de frame.

Cette POC réalise les deux premières opérations seulement. `fn.frames()` et
`fn.lus()` peuvent fournir des candidats par nom, mais ils ne choisissent pas
une frame pour une occurrence en contexte. Une vraie analyse exige un parser
sémantique de frames ou un adaptateur propre combinant lexique, syntaxe et
contexte.

## Rapport à l'architecture

Les frames, unités lexicales et relations sont des ressources externes
attribuées à FrameNet 1.7. Les annotation sets sont des analyses de corpus
existantes, non des vérités produites par le système cognitif. Le moteur peut
les exploiter comme inventaire de candidats, exemples, contraintes de valence
ou liens entre concepts, mais doit conserver leurs identifiants, leur version,
leur empreinte de ressource et la provenance de l'adaptateur.

Les mappings d'éléments associés aux relations sont importants : une relation
d'héritage entre deux frames n'autorise pas à confondre leurs éléments sans
garder la direction et le type de relation. De même, `Core`, `Peripheral` et
`Extra-Thematic` sont des catégories FrameNet, pas des degrés de vérité.

## Limites

- La POC porte sur FrameNet 1.7 en anglais via NLTK 3.10.3.
- La valence nécessite la lecture complémentaire du XML, car l'API NLTK ne
  l'expose pas ; cette dépendance est testée et signalée dans chaque résultat.
- Le total de 202 403 exemples provient des compteurs `annotated` des unités
  lexicales. La POC n'énumère pas toutes les annotations full-text pour
  fabriquer un total global d'occurrences.
- Certaines unités lexicales ou annotations de la ressource portent des
  statuts de travail ; les statuts natifs sont conservés et ne sont pas
  transformés en scores de confiance.
- Aucun score n'est fourni pour les annotations manuelles choisies, et aucun
  score artificiel n'est ajouté.
- La détection de cibles, la désambiguïsation de frames et l'étiquetage
  automatique des éléments sur une phrase nouvelle ne sont pas réalisés.
