# Verdict NLP-02

## Verdict

**GO** pour obtenir les trois représentations avec ACE/ERG/PyDelphin.
**PARTIEL** si EDS ou DMRS doit remplacer la MRS sans perte.

Sur les 21 candidats observés :

- 18 MRS sont bien formées selon PyDelphin ;
- 8 candidats contiennent le prédicat de repli `unknown` ;
- 4 portent des contraintes `ICONS`, absentes des projections EDS/DMRS ;
- 5 reconstructions DMRS → MRS seulement sont isomorphes à la MRS source ;
- sur 150 occurrences de rôles comparables, 114 sont directement préservées
  dans EDS et 120 dans DMRS.

Les candidats problématiques restent conservés comme observations externes ;
ils ne sont ni supprimés ni présentés comme équivalents aux lectures propres.

## Champs effectivement obtenus

- MRS : `TOP`, `INDEX`, surface, prédicats, identifiants de variables,
  propriétés morphosémantiques, labels, rôles `ARG*`, `RSTR`, `BODY`, constantes
  `CARG`, charspans `lnk`, `HCONS` et `ICONS` (présents dans quatre candidats).
- EDS : `top`, nœuds identifiés, prédicats, types et propriétés, `CARG`, `lnk`,
  et arêtes étiquetées, dont `BV` pour le lien quantificateur–variable.
- DMRS : `top`, `index`, nœuds numériques, prédicats, sortinfo/propriétés,
  `CARG`, `lnk`, et liens avec rôle et post (`NEQ`, `EQ`, `H`, `HEQ`).

## Pertes observées lors des conversions

| Information MRS | MRS → EDS | MRS → DMRS |
|---|---|---|
| Occurrences de prédicats | conservées | conservées |
| Ancres `lnk` des prédicats | conservées | conservées |
| Types/propriétés des variables intrinsèques | portés par les nœuds | portés par les nœuds |
| Rôles non scopaux | conservés si leur cible devient un nœud ; sinon absents | conservés si leur cible devient un nœud ; sinon absents |
| Liaison des quantificateurs | reformulée en `BV` | reformulée en `RSTR/H` |
| `TOP` / `INDEX` | `TOP` seulement ; pas d'`INDEX` distinct | les deux sont présents, sans garantir un aller-retour isomorphe |
| IDs bruts des variables et handles | perdus ou réaffectés | remplacés par des IDs de nœuds |
| Labels et `HCONS` bruts | perdus | perdus ; portée utile projetée en `H/HEQ` |
| Sous-spécification de portée | perdue | encodée par les liens scopaux, sans les identités `HCONS` brutes |
| `ICONS` | non représenté | non représenté |
| Arguments de handles sans cible explicite, dont certains `BODY` | perdus | pas de lien explicite |

Ainsi, MRS doit rester disponible comme source de vérité externe si le moteur a
besoin des identités de variables/handles ou des contraintes de portée
complètes. EDS et DMRS sont des vues complémentaires, pas des remplacements
sans perte.

## Limites

- Toutes les analyses rendues sont conservées, mais elles restent bornées par
  `--max-results`. `limit_reached = true` indique seulement que cette borne a
  été atteinte, pas le nombre total réel de lectures.
- Quatre candidats rendent la perte d'`ICONS` directement observable : les
  modèles EDS/DMRS PyDelphin ne possèdent pas de champ correspondant.
- L'égalité des prédicats et des ancres est validée automatiquement. Les pertes
  de portée sont des propriétés structurelles des modèles et sont rendues
  visibles par les listes `HCONS` et `dmrs_scopal_links` dans les résultats.
- `plausibly_scopes` est explicitement une validation heuristique PyDelphin,
  pas une énumération des portées possibles ni une preuve complète de
  satisfaisabilité transitive.

## Alignement avec l'architecture

- Le texte source demeure une observation séparée, avec identité, span complet
  et convention d'offset explicitée pour ces fixtures ASCII. Le comportement
  Unicode exact reste volontairement réservé à `NLP-04`.
- Chaque lecture est un candidat distinct avec support, rang, score éventuel,
  producteur, méthode de conversion et empreintes des sérialisations brutes.
  Un `semantic_id` commun signale sans les fusionner les lectures qui ont une
  MRS identique.
- Les projections EDS/DMRS pointent vers la MRS dont elles dérivent ; elles ne
  remplacent ni la source ni la MRS.
- Les lectures concurrentes coexistent jusqu'à la limite configurée et aucun
  `argmax` ne les élimine.
- Aucun prédicat ERG n'est transformé en catégorie cognitive interne. Les noms
  tels que `_chase_v_1` restent explicitement attribués à ACE/ERG.

Cette enveloppe prouve la compatibilité avec les invariants architecturaux,
mais ne prétend pas définir le contrat commun définitif, qui relève de
`GRAPH-02`.

## Exemples linguistiques concrets

### Quantification et portée

Phrase analysée : **“Every dog chased a cat.”**

En langage courant, cette phrase peut décrire au moins deux situations :

- chaque chien a poursuivi un chat, éventuellement un chat différent pour
  chaque chien ;
- il existe un chat particulier que tous les chiens ont poursuivi.

La MRS représente bien les deux quantificateurs, « every » et « a », et laisse
leur portée sous-spécifiée plutôt que de choisir arbitrairement une lecture.
EDS conserve que « dog » est l'agent de « chase » et « cat » son objet, mais ne
conserve pas cette ambiguïté de portée. Pour cette première lecture, DMRS garde
assez de structure scopale pour reconstruire une MRS isomorphe, même si les
identifiants de handles sont recréés. Ni EDS ni DMRS n'énumère toutefois les
deux interprétations en phrases logiques séparées.

Point crucial : les trois analyses ACE renvoyées pour cette phrase ne sont pas
les trois lectures de portée. La première est l'analyse attendue. Les deux
autres sont des analyses de repli contenant `unknown` ; l'une d'elles n'est
même pas une MRS bien formée. Quant aux deux interprétations « un chat par
chien » et « un même chat pour tous », elles relèvent de NLP-03. NLP-02 doit
seulement démontrer que la MRS sous-spécifiée contient les contraintes à partir
desquelles ces lectures pourront être étudiées.

### Négation

Phrase analysée : **“Kim did not leave.”**

L'analyse ne dit pas simplement qu'il existe un départ et une négation
indépendants. Elle indique que la négation porte sur l'événement « Kim part » :
c'est le départ de Kim qui est nié. MRS exprime cette portée au moyen d'un
handle et d'une contrainte `qeq`. EDS la transforme en une dépendance entre la
négation et l'événement de départ ; DMRS la représente par un lien scopal.

### Pronom réfléchi

Phrase analysée : **“She sees herself.”**

Un humain comprend normalement que « she » et « herself » désignent la même
personne. ERG produit bien deux expressions pronominales et relie la première
au rôle de sujet de « see » et la seconde au rôle d'objet. En revanche, la
sortie observée emploie deux variables référentielles distinctes et ne fournit
pas ici de lien explicite affirmant leur coréférence. La POC ne doit donc pas
inventer l'identité entre les deux : sa résolution exige une information ou un
traitement supplémentaire.

### Proposition relative

Phrase analysée : **“The dog that chased the cat barked.”**

La structure obtenue exprime que le chien accomplit deux actions : il est celui
qui poursuit le chat et celui qui aboie. Le chat est uniquement l'objet de la
poursuite. Le partage du même participant « dog » entre la relative et la
proposition principale est conservé dans MRS, EDS et DMRS, même si les trois
formats l'encodent différemment.

### Coordination

Phrase analysée : **“Kim sang and danced.”**

L'analyse contient deux événements, chanter et danser, reliés par la
coordination « and ». Kim est l'agent des deux événements. EDS rend directement
visible ce partage du participant ; DMRS conserve en plus le type des liens
entre la coordination et les deux événements.

Ces exemples illustrent la limite essentielle de la POC : les représentations
structurent des interprétations linguistiques candidates, mais ne décident ni
quelle lecture de portée est vraie, ni à qui un pronom réfère dans le monde, ni
si le contenu de la phrase doit devenir une connaissance interne.
