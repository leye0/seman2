# Verdict LEX-03

## Verdict

**PARTIEL COMME LECTEUR DE CORPUS, AVEC INVENTAIRE DE ROLESETS EXPLOITABLE.**

NLTK PropBank expose bien les définitions de rolesets, les descriptions des
arguments numérotés, les correspondances VerbNet, les exemples des fichiers de
frames et les instances annotées de `prop.txt`. Lorsqu'un arbre du Treebank
installé est disponible, chaque prédicat et argument peut être ramené à son
pointeur natif, sa position dans l'arbre et ses terminaux.

La limite est matérielle et importante : les annotations couvrent tout le Wall
Street Journal de PropBank 1.0, tandis que le Treebank libre livré par NLTK
n'est qu'un échantillon. Cette installation résout 9 353 annotations sur
112 917 contre un arbre ; 103 564 instances conservent leur ligne et leurs
pointeurs, mais pas l'arbre correspondant. Le paquet NLTK `ptb` a aussi été
téléchargé : il contient le catalogue `allcats.txt` de 2 504 fichiers, mais
zéro arbre `.MRG`. Le Penn Treebank complet demeure un produit distinct sous
licence que NLTK ne peut pas redistribuer.

## Données observées

La ressource installée contient :

- 3 257 lemmes verbaux ;
- 4 659 rolesets ;
- 112 917 instances annotées ;
- 199 fichiers Treebank installés ;
- 2 504 entrées dans le catalogue du paquet NLTK `ptb`, mais zéro `.MRG` ;
- 9 353 instances dont l'arbre est localement résoluble ;
- 1 485 annotations portant l'un des 101 identifiants `.XX` non résolus ;
- 251 formes de labels d'arguments dans les annotations natives.

Les huit fixtures retiennent sept lemmes, huit identifiants de rolesets et 26
arguments. Elles couvrent les pointeurs simples, scindés, chaînés et une chaîne
contenant elle-même un pointeur scindé. Les numéros de terminaux sont indexés à
partir de zéro et comptent les catégories vides et les traces.

## Exemples en langage humain

### `give.01` décrit les rôles, l'instance les localise

Le roleset `give.01`, nommé « transfer », décrit `ARG0` comme le donneur,
`ARG1` comme la chose donnée et `ARG2` comme le destinataire. Il les relie aux
rôles VerbNet `Agent`, `Theme` et `Recipient` de la classe `13.1-1`.

Dans l'instance **“the executives gave the chefs a standing ovation”**, la
ligne PropBank choisit déjà `give.01` et pointe respectivement vers les trois
constituants. La POC conserve séparément la définition lexicale et cette
annotation de corpus : la définition ne suffit pas à retrouver seule les
arguments d'une phrase inconnue.

### `run` montre que le lemme ne choisit pas le sens

`propbank.rolesets("run")` retourne neuf rolesets. Deux instances annotées
illustrent notamment :

- `run.01`, « operate », dans **“running the company”** ;
- `run.02`, « walk quickly », dans **“run for home”**.

Le choix différent est inscrit dans `prop.txt`. L'appel lexical retourne les
neuf définitions et ne classe pas une nouvelle occurrence de `run`.

### Les pointeurs ne sont pas toujours des spans simples

Dans une instance de `say.01`, `ARG1` est un pointeur chaîné reliant la
proposition topicalisée et sa trace. Dans une instance de `stop.01`, `ARG1` est
scindé entre plusieurs morceaux correspondant à **“using crocidolite in its
Micronite cigarette filters”**.

La POC préserve la notation native, le type du pointeur, ses composants, les
positions NLTK dans l'arbre, les indices de terminaux et le sous-arbre
sélectionné. Aplatir ces objets en un seul intervalle textuel ferait perdre les
traces, discontinuités et relations syntaxiques.

L'instance `expose.01` vérifie en plus la forme imbriquée
`chain(split(tree,tree,tree),tree)`. Son label natif `ARG2-to` est conservé tel
quel, tout en exposant séparément le rôle numéroté `ARG2` et le suffixe `to`.

### Les rolesets `.XX` restent explicitement non résolus

PropBank contient 1 485 annotations gold dont le roleset se termine par `.XX`.
Dans la fixture `note.XX`, la POC ne fabrique aucune définition : elle conserve
l'identifiant annoté avec `roleset_definition_status =
unresolved_in_corpus_annotation`, tout en présentant `note.01` et `note.02`
comme candidats lexicaux complets et non sélectionnés.

## Frontière entre ressource et analyse automatique

Trois opérations doivent rester distinctes :

1. le lookup d'un lemme retourne toutes ses définitions de rolesets ;
2. la consultation d'une coordonnée PropBank retourne une annotation humaine
   existante, avec le roleset et les arguments déjà choisis ;
3. l'annotation d'une phrase nouvelle exigerait un semantic role labeler ou un
   adaptateur propre combinant analyse syntaxique, candidats lexicaux et
   contexte.

Cette POC réalise les deux premières opérations seulement. Elle ne doit pas
être présentée comme une capacité de semantic role labeling automatique.

Chaque candidat lexical possède un identifiant stable, son producteur, la
version et l'empreinte SHA-256 de la ressource, ainsi que des liens explicites
vers les autres candidats du même lookup. Les annotations portent aussi la
version de l'adaptateur et du schéma.

## Rapport à l'architecture

Les définitions PropBank sont des ressources lexicales externes et les lignes
de `prop.txt` sont des analyses attribuées à un corpus. Le moteur peut les
utiliser comme exemples, candidats de rôles et clés d'alignement vers VerbNet
ou SemLink, sans convertir automatiquement `ARG0` en « agent » ni le roleset
annoté en vérité cognitive.

Pour les données d'entraînement ou d'évaluation nécessitant tous les arbres,
il faudra soit fournir un Penn Treebank licencié, soit travailler uniquement
sur le sous-ensemble NLTK, soit conserver les pointeurs non résolus avec leur
provenance. L'alignement d'une occurrence nouvelle relève de LEX-07.

## Limites

- La POC utilise PropBank 1.0 en anglais via NLTK 3.10.3.
- Les arbres disponibles proviennent de l'échantillon Penn Treebank de NLTK.
- Les textes reconstruits depuis les feuilles d'arbre ne restituent pas la
  typographie originale et incluent explicitement les traces dans la vue
  structurelle. Les charspans originaux sont donc `null` avec une raison
  explicite ; ils ne sont jamais inventés depuis ce texte reconstruit.
- Les descriptions d'arguments dépendent du roleset ; les `ARGM-*` sont des
  modificateurs généraux et n'ont pas une description numérotée locale.
- La désambiguïsation du roleset et l'étiquetage d'une phrase nouvelle ne sont
  pas réalisés.
