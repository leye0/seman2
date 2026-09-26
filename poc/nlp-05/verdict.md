# Verdict NLP-05

## Verdict

**GO** pour Link Grammar comme producteur d'analyses syntaxiques
complémentaires et concurrentes.

La POC obtient bien tous les champs demandés par `required_poc.md` :

- tokens avec forme analysée, tranche source, offsets caractères et octets,
  disjoncteur et coût local ;
- liens typés avec connecteurs gauche/droit, extrémités, longueur et support
  textuel dérivé ;
- tous les linkages retournés jusqu'à la limite, chacun doté d'un identifiant
  stable, d'un rang et de ses différences avec le premier ;
- coûts de mots inutilisés, de disjoncteurs et de liens, ainsi que le nom d'une
  éventuelle violation ;
- arbre de constituants natif et version structurée dont les feuilles sont
  reliées aux tokens ;
- échec de segmentation, échec strict, récupération partielle et troncature
  potentielle représentés séparément.

Sur les cinq fixtures, Link Grammar renvoie 25 linkages stricts et 225 liens
typés. Les 25 arbres de constituants sont disponibles et les 25 partitions de
tokens permettent de reconstituer exactement la source. La limite de 100 n'est
atteinte par aucune fixture.

## Ce que montrent concrètement les phrases

### Phrase simple

Pour **“The dog chased the cat.”**, Link Grammar relie `dog` à `chased` par un
lien sujet `Ss*s`, puis `chased` à `cat` par un lien objet `Os`. Les liens `D`
attachent chaque déterminant `the` à son nom. L'arbre obtenu contient le groupe
nominal sujet, le groupe verbal et le groupe nominal objet.

Même cette phrase produit deux linkages. Ils partagent l'analyse linguistique
principale, mais diffèrent par certains liens au mur gauche et par leurs coûts.
La POC les conserve tous les deux au lieu de décider qu'ils sont identiques.

### Ambiguïté d'attachement

Pour **“I saw the man with the telescope.”**, 16 linkages sont retournés. Deux
structures importantes sont effectivement présentes :

- au rang 3, le lien `MVp` va de `saw` à `with` et le PP est sous le groupe
  verbal : la lunette peut être comprise comme l'instrument utilisé pour voir ;
- au rang 5, le lien `Mp` va de `man` à `with` et le PP est inclus dans le
  groupe nominal : il peut s'agir de l'homme qui possède ou porte la lunette.

Les autres alternatives combinent notamment ces attachements avec deux entrées
lexicales de `saw`. Les 16 candidats ne correspondent donc pas à 16 sens
nécessairement distincts ; ce sont 16 linkages produits par l'outil, conservés
comme tels avec leurs différences observables.

### Comment les phrases autour peuvent lever l'ambiguïté

Link Grammar analyse ici une phrase isolée. Ses coûts ordonnent les linkages
selon son dictionnaire et son modèle syntaxique, mais l'outil ne consulte pas
les phrases précédentes ou suivantes pour décider ce que le locuteur voulait
dire. Il ne faut donc pas interpréter le premier des 16 linkages comme la
lecture définitivement correcte.

Le moteur cognitif pourra en revanche confronter ces candidats aux autres
observations disponibles :

- **“He was carrying it.”** rend plus plausible la lecture où `with the
  telescope` décrit `the man` ;
- **“I used it to see farther.”** rend plus plausible la lecture où le
  télescope est l'instrument de l'action `saw` ;
- les mentions antérieures, la résolution de `he` et `it`, les relations de
  discours, les connaissances actives et les analyses d'autres outils peuvent
  fournir des indices supplémentaires.

Le choix contextuel ne devrait toutefois pas porter naïvement sur 16 numéros.
Plusieurs linkages ne diffèrent que par une entrée lexicale, un lien technique
ou un coût, tout en soutenant la même hypothèse pertinente — par exemple
« attachement au verbe » ou « attachement au nom ». L'adaptateur commun devra
permettre de reconnaître ces ressemblances à partir des structures observées.
Le moteur pourra alors pondérer des candidats ou des groupes de candidats avec
le contexte, sans perdre les linkages originaux, leurs coûts ni leur
provenance.

Si les indices contextuels ne suffisent pas, plusieurs hypothèses doivent
rester actives. L'architecture ne demande pas une décision arbitraire à chaque
ambiguïté : elle demande que les analyses concurrentes puissent coexister et
être réévaluées lorsqu'une observation ultérieure apporte de l'information.

NLP-05 démontre que les alternatives et leurs différences sont disponibles.
NLP-06 devra déterminer lesquelles apportent une information complémentaire à
ERG et lesquelles sont surtout des variantes redondantes. La construction du
contexte discursif, la coréférence et la pondération cognitive appartiennent à
leurs composants architecturaux respectifs, pas à Link Grammar lui-même.

### Coordination

Pour **“Kim sang and Sandy danced.”**, l'arbre contient deux constituants `S`
coordonnés par `and`. Des liens sujet relient respectivement `Kim` à `sang` et
`Sandy` à `danced`. Six linkages concurrents sont disponibles.

### Fragment

Pour **“In the garden.”**, Link Grammar accepte le fragment sans liens nuls. Il
produit un linkage et un constituant nominal `the garden` gouverné par `in`.
Un fragment n'est donc pas assimilé automatiquement à un échec.

### Entrée non grammaticale

Pour **“Dog the quickly.”**, la passe stricte (`max_null_count = 0`) trouve
zéro linkage. Ce résultat est stocké comme `strict_parse_failure` et non comme
une liste ambiguë ou une exception perdue.

Une seconde passe diagnostique autorisant deux liens nuls trouve deux linkages,
mais chacun a `unused_word_cost = 2`. Ils sont explicitement marqués
`partial_parse_with_null_links` et `is_full_parse = false`; ils ne remplacent
jamais l'échec strict.

## Rapport à l'architecture

Le texte source demeure une observation autonome. Chaque linkage possède sa
provenance Link Grammar, pointe vers cette observation et conserve les résidus
non lexicaux. Les formes morphologiques comme `dog.n` ou `chased.v-d` restent
des annotations de l'analyseur : elles ne remplacent jamais les tranches
originales `dog` et `chased`.

Les supports textuels des liens sont dérivés de leurs deux tokens. La POC les
marque avec `direct_lnk = null` afin de ne pas inventer un ancrage natif que
Link Grammar ne fournit pas au lien lui-même.

## Limites

- Les codes de liens (`Ss*s`, `Os`, `MVp`, etc.) appartiennent au dictionnaire
  anglais Link Grammar. Leur interprétation doit rester attribuée à cet outil.
- Les coûts servent à comparer les linkages selon le modèle Link Grammar ; ce
  ne sont pas des probabilités ni des degrés de vérité architecturale.
- Une limite atteinte signifie que l'ensemble retourné peut avoir été
  échantillonné. Le champ `limit_reached_or_sampled` interdit de présenter cet
  ensemble comme exhaustif.
- La POC valide le dictionnaire anglais livré localement. Elle ne démontre pas
  la même couverture pour d'autres langues.
- La question de savoir ce que Link Grammar ajoute réellement à ERG appartient
  à NLP-06.
