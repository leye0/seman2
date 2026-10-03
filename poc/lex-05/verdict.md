# Verdict LEX-05

## Verdict

**PARTIEL À CAUSE DE L'ÉCART ENTRE LES VERSIONS CIBLÉES PAR SEMLINK 2 ET LES
RESSOURCES NLTK INSTALLÉES.**

SemLink 2 fournit bien des tables PropBank→VerbNet et VerbNet→FrameNet, ainsi
que des annotations d'occurrences qui combinent rôles PropBank, rôles VerbNet
et, lorsqu'ils existent, éléments FrameNet. Il ne fournit pas de lien WordNet
direct dans ces deux JSON : ce lien doit être suivi depuis les clés `wn` des
membres VerbNet.

Le dépôt SemLink annonce explicitement VerbNet 3.3, Unified PropBank et
FrameNet 1.7. Or l'installation locale NLTK 3.10.3 expose VerbNet 2.1,
PropBank 1.0, WordNet 3.0 et FrameNet 1.7. La POC refuse donc de qualifier
d'« absente » une clé SemLink simplement parce qu'elle manque dans une version
NLTK plus ancienne : elle distingue absence dans la table, échec de jointure et
écart de version.

## Inventaire SemLink observé

La révision installée contient :

- 148 653 instances annotées ;
- 4 177 clés de rolesets dans `pb-vn2.json`, donnant 5 279 arêtes
  PropBank→VerbNet ;
- 818 rolesets associés à plusieurs classes VerbNet ;
- 1 681 clés classe+membre dans `vn-fn2.json`, donnant 2 385 arêtes
  VerbNet→FrameNet ;
- 488 clés VerbNet associées à plusieurs frames ;
- 111 258 annotations d'arguments reliant PropBank à un rôle VerbNet, dont
  35 896 portent aussi un élément FrameNet.

Parmi les occurrences, 147 742 ont un roleset PropBank, 97 032 une classe
VerbNet, 43 237 une frame assignée et 48 459 un groupe de sens OntoNotes. La
colonne FrameNet contient aussi 21 539 marqueurs `IN`, 11 669 marqueurs `NF` et
72 208 valeurs `None`. Le code de construction SemLink définit `IN` comme un
cas à plusieurs mappings, `NF` comme l'absence de mapping produit, et `None`
comme l'absence d'annotation stockée.

## Taux de jointure avec les versions installées

Les jointures Polars utilisent exclusivement les clés natives exactes ; les
dénominateurs et numérateurs complets sont conservés dans `join-rates.json`.

Pour les 5 279 arêtes PropBank→VerbNet :

- 3 436 rolesets, soit 65,09 %, existent dans PropBank 1.0 installé ;
- 4 373 classes, soit 82,84 %, existent dans VerbNet 2.1 ;
- 3 565 couples classe+membre, soit 67,53 %, existent dans VerbNet 2.1 ;
- 2 301 arêtes, soit 43,59 %, résolvent simultanément le roleset et le membre ;
- 2 903 arêtes, soit 54,99 %, atteignent un membre portant des clés WordNet,
  toutes résolues dans WordNet 3.0 après normalisation documentée.

Pour les 2 385 arêtes VerbNet→FrameNet :

- 1 790 membres VerbNet sont résolus, soit 75,05 % ;
- 2 379 frames existent, soit 99,75 % ;
- 2 322 couples frame+lemme existent, soit 97,36 % ;
- 1 758 arêtes résolvent les deux extrémités, soit 73,71 %.

Les annotations d'occurrences confirment le même contraste : 95,51 % des
assignations PropBank présentes se résolvent, contre 43,44 % des couples
classe+membre VerbNet et 97,67 % des couples frame+lemme FrameNet. Parmi les
paires PB-VN applicables, 83,95 % figurent dans la table lexicale courante ;
pour les triplets VN-lemme-FN, ce taux est de 72,42 %.

Les rôles sont également contrôlés. Sur 111 258 liens d'arguments, 98,30 % des
arguments PropBank et 68,86 % des rôles VerbNet se résolvent contre les
versions installées. Parmi les 35 775 liens possédant à la fois une frame
assignée et un élément FrameNet, 90,10 % des éléments sont résolus.

## Exemples en langage humain

### `join.01` conserve plusieurs frames possibles

SemLink relie `join.01` à la classe VerbNet `22.1-2-1`, avec `ARG0→Agent`,
`ARG1→Patient` et `ARG2→Co-Patient`. Le couple `22.1-2-1 + join` mène à deux
frames : `Attaching` et `Cause_to_amalgamate`.

L'instance `wsj_0001.parse / 0 / 8` choisit déjà
`Cause_to_amalgamate`. Ses annotations relient notamment `ARG0` à `Agent` puis
à l'élément FrameNet `Agent`, et `ARG1` à `Patient` puis à `Part_1`. Ce choix
vient du corpus SemLink ; la table lexicale seule conserve les deux frames.

Le membre VerbNet installé porte trois clés WordNet, résolues vers les synsets
`join.v.02`, `join.v.04` et `connect.v.03`. Ce sont des liens de sens candidats,
pas trois synonymes automatiquement interchangeables dans le contexte.

L'ancien VerbNet ne résout pas `Co-Patient` sur cette sous-classe : son parent
2.1 utilise notamment `Patient1` et `Patient2`. Cette différence est conservée
comme échec de jointure de rôle, et non corrigée par une équivalence inventée.

### `buy.01` fournit une chaîne complète

`buy.01` mène à `13.5.1`, puis à `Commerce_buy`. Le membre `buy` de VerbNet
2.1 porte deux clés WordNet résolues vers `buy.v.01` et `buy.v.03`. Dans
l'instance `wsj_0029.parse / 12 / 14`, `ARG0→Agent→Buyer` et
`ARG1→Theme→Goods` sont entièrement résolus.

Cette fixture montre une chaîne techniquement complète, mais chaque arête
garde son type et sa source : roleset→classe, argument→rôle, membre→clé de sens
et classe+membre→frame.

### `accept.01` montre multiplicité et incompatibilité partielle

La table associe `accept.01` à trois classes : `13.5.2`, `29.2-1-1` et `77.1`.
Les deux premières existent dans VerbNet 2.1 ; `77.1` n'y existe pas. La
première mène en outre aux frames `Receiving` et `Respond_to_proposal`.

L'instance sélectionnée porte donc le marqueur `IN` au lieu de forcer un choix
entre ces frames. La POC expose tous les candidats et ne transforme pas `IN` en
frame réelle.

### Une annotation d'instance ne garantit pas une table lexicale

L'instance `wsj_0001.parse / 1 / 10` contient `publish.01` et la classe
`26.4`, mais ni `publish.01` dans `pb-vn2.json`, ni `26.4-publish` dans
`vn-fn2.json`. C'est un mapping absent des tables courantes, distinct d'une clé
présente mais non résolue localement.

À l'inverse, `adjoin.01` est bien présent dans SemLink et mène à `47.8-1`, aux
clés WordNet du membre puis à `Adjacency`, mais le roleset Unified PropBank
n'existe pas dans PropBank 1.0 installé. Il s'agit ici d'un écart de version.

## Types de relations et absence d'identité

La sortie représente explicitement quatre types de liens :

1. `propbank_roleset_maps_to_verbnet_class` ;
2. `propbank_argument_maps_to_verbnet_role` ;
3. `verbnet_member_has_wordnet_sense_key` ;
4. `verbnet_class_member_maps_to_framenet_frame`.

Les occurrences peuvent ajouter
`verbnet_role_maps_to_framenet_frame_element`. Le fichier historique
`VN-FNRoleMapping.txt` est présent, mais date de 2006 ; il n'est pas fusionné
silencieusement avec les mappings SemLink 2 actuels.

Aucune de ces relations n'est traitée comme une identité. Une chaîne transitive
PB→VN→FN ne prouve pas qu'un roleset, une classe et une frame sont le même objet
sémantique. Elle fournit des candidats et des correspondances attribuées.

## Rapport à l'architecture

SemLink est utilisable comme couche de pont externe à condition de conserver :

- la direction et le type de chaque arête ;
- les identifiants natifs et la version de chaque vocabulaire ;
- les alternatives multiples et les marqueurs `IN`, `NF` et `None` ;
- les clés non résolues avec leur cause ;
- la différence entre table lexicale et annotation d'occurrence.

Pour une intégration fiable, il faut installer les versions ciblées par
SemLink 2 — surtout VerbNet 3.3 et Unified PropBank — ou versionner des
adaptateurs de migration explicites. Les taux actuels interdisent de considérer
un échec de jointure comme une absence sémantique.

## Limites

- La POC audite la révision SemLink
  `2636bf5a4ae9c93b669a1184a8aaae9ca21552d3`.
- Les ressources NLTK installées ne correspondent pas toutes aux versions de
  construction de SemLink 2.
- Les clés WordNet proviennent de VerbNet 2.1 installé, pas directement de
  SemLink. VerbNet omet les deux champs vides terminaux des clés ; l'adaptateur
  ajoute `::` et retire le préfixe d'incertitude `?` avant le lookup, tout en
  conservant la clé source.
- Les annotations complètes OntoNotes et leurs arbres ne sont pas installés ;
  la POC conserve donc les coordonnées et pointeurs SemLink sans reconstruire
  le texte source.
- Aucun alignement ni choix de sens n'est effectué sur une phrase nouvelle.
