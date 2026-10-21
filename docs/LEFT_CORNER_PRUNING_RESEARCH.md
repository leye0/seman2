# Faisabilité lexicale à gauche et qualité grammaticale

## Hypothèse

Le reconnaisseur vectoriel construit des états de règles partiels qui attendent
un prochain constituant à un offset exact, même lorsqu'aucune lecture lexicale
ne pourrait amorcer ce constituant à cet offset. Ces états ne sont pas des
analyses complètes et ne peuvent mener à aucun arbre fini.

L'option de recherche `Parser(..., lexical_left_corner_pruning=True)`
calcule la fermeture transitive **des premières catégories** de chaque
non-terminal à partir des règles existantes. Pour un état `(règle, dot, début,
fin)`, elle compare les premières catégories possibles de la prochaine
composante à **toutes** les catégories du treillis lexical qui commencent à
`_next_start(fin)`. Si l'intersection est vide, la continuation est
impossible; l'état n'est pas matérialisé. Elle ne supprime aucune lecture
WordNet, aucun trait morphosyntaxique ni aucune règle du projet.

L'invariant exige des productions grammaticales non vides et des arêtes
lexicales de longueur positive. Les catégories récursives se traitent par
point fixe; toute catégorie peut aussi être directement lexicale.

## Vérifications du 21 octobre 2026

- [Comparaison contrôlée sur 17 phrases](https://github.com/leye0/seman2/actions/runs/39593270603) :
  502 326 états partiels contre 158 910 (-68,4 %). Sur les 15 analyses
  initialement non saturées : nœuds de forêt, dérivations et arbres identiques.
  Les deux autres étaient censurées par budget.
- [Essai du corpus immuable de 500 phrases](https://github.com/leye0/seman2/actions/runs/39593587242) :
  455/500 analyses terminées contre 447/500 avant, même empreinte de cohorte
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
  Les huit récupérations sont les cas 229, 235, 243, 248, 359, 363,
  367 et 485. **Aucun cas déjà reconnu ne devient non reconnu.**
  Aucune saturation de forêt n'est rapportée dans cet essai, contre
  29 drapeaux de saturation (dont des phrases réussies) au témoin précédent.
- Six meilleures racines changent parmi les phrases déjà reconnues :
  104, 231, 350, 477, 488, 499. Le témoin était saturé pour chacune;
  ce ne sont donc pas des régressions d'une recherche antérieure complète.
  Ce sont néanmoins des changements **de qualité** qui exigent un contrôle.

## Verdict linguistique : pas encore validé pour la production

Une reconnaissance `completed=True` n'est pas une garantie de syntaxe
correcte. L'inspection des arbres optimisés a trouvé notamment :

- **Cas 485** : `drank up the vapours` séparé en `drank` et
  `up the vapours`, ce dernier projeté comme impératif indépendant.
  Le rattachement du syntagme verbal et de la particule est faux.
- **Cas 248** : `The turn of your countenance I` projeté comme NP
  sujet de `shall never forget`, absorbant à tort le pronom sujet
  `I` dans le groupe nominal topicalisé.
- **Cas 499** : `For my part` interprété comme une coordination en tête
  suivie d'un NP disloqué plutôt que comme un complément prépositionnel
  cadratif.
- **Cas 104** : `Peggotty's eyes were` détaché comme copule elliptique,
  avec `full of compassion` absorbé par une construction nominale
  disloquée au lieu d'un attribut du sujet.

Ces quatre classes sont documentées par des contre-exemples
`@unittest.expectedFailure` dans
`superparser/tests/test_left_corner_tree_quality.py`. Elles ne doivent pas
être corrigées par retrait arbitraire de catégories, par bonus de score ou
par règles spécifiques aux phrases. Il faut examiner la **licence générale**
des dislocations nominales, de l'ellipse copulaire, des coordonnées et du
rattachement du groupe verbal, puis confronter chaque hypothèse à des
contrastes grammaticaux et à la cohorte complète.

**Décision :** l'optimisation demeure désactivée par défaut en attendant
un audit structurel de qualité, malgré le gain technique prouvé.

## Contrôles transversaux sur l'ensemble des meilleurs arbres

Un balayage du fichier `per_sentence.jsonl` expérimental, sans sélection
préalable de phrases, relève les signaux suivants parmi les 455 arbres
complétés :

| Signal structurel à inspecter | Phrases concernées |
| --- | ---: |
| Construction `clause_front_np` quelque part dans l'arbre | 54 |
| `clause_cop_ellipsis` quelque part dans l'arbre | 17 |
| Impératif imbriqué commençant après du texte alphabétique (sans ponctuation intermédiaire vérifiée) | 12 |
| NP de plus de trois mots se terminant par un pronom personnel écrit | 11 |
| `coord_clause` initial introduit par `For` | 2 |

Ce sont des **signatures de recherche**, pas des verdicts : un impératif
imbriqué ou un constituant nominal antéposé peut être parfaitement
grammatical. Les compteurs sont des nombres de **phrases distinctes**,
non des occurrences; une même phrase peut avoir plusieurs signaux.

Cette vue globale oriente une suite d'expériences vers les mécanismes
communs (licence des dislocations nominales et des ellipses, séparation
des prédicats et de leurs compléments), plutôt que des règles qui
cibleraient un titre de roman ou un indice particulier.

## Révision des coordinations non propositionnelles

Le lexique possède déjà un trait positif `nominal_coordination=true` pour
`and`, `but`, `or`, `nor` et `yet`. La conjonction causale `for` est une
lecture `COORD` grammaticalement justifiée **entre deux propositions**,
mais non comme coordination de deux NP, VP, PP ou ADJP. Toutes les règles
non propositionnelles employant `COORD` exigent désormais la preuve
positive de ce trait lexical : la possibilité `for/COORD` reste dans le
treillis, elle est simplement rejetée lorsque la composition est
non propositionnelle. Les règles de catégorie `CLAUSE` gardent la lecture
causale. Ce contrôle constitue une contrainte grammaticale générale et non
un ajustement de score pour le corpus. La qualité des nouveaux arbres doit
être mesurée séparément du taux de complétion.

## Coordination causale finie

L'emploi causal de `for` conserve sa lecture lexicale `COORD` (ainsi que
`PREP`). Il est maintenant distingué par `causal_coordination=true`.
La règle `coord_clause` demeure réservée aux coordonnants discursifs
non causaux. La règle `coord_clause_causal_finite` exige un sujet NP
et un prédicat VP *fini* dont les traits d'accord s'unifient. Elle empêche
les expressions prépositionnelles initiales `For my part` et
`As for the captain` de se faire passer pour un préfixe coordonnant
suivi d'une proposition disloquée. Le lien sémantique AGENT est conservé
pour le sujet et son prédicat.

Après introduction de `coord_clause_causal_finite`, le contrôle
`For my part` n'est plus un échec attendu : il est désormais un test de
non-régression positif. Pour la parité trie/canonique, l'identité des
meilleurs arbres ne constitue une obligation que pour deux forêts non
saturées ; le diagnostic de saturation demeure explicitement observable,
plutôt que prétendre à la certification d'un ordre sur une forêt partielle.

## Appositions nominales et reprises pronominales

Une projection directe de `PRONOUN` dans un groupe NP porte
`pronominal=true`. Un appositif nominal attend maintenant
`pronominal=false` : un pronom sujet comme `he` dans `The captain,
he waited` ne peut plus être fusionné à la première NP. La
construction de dislocation gauche `NP, CLAUSE` reste disponible, tout
comme les appositions de type `John, the doctor`. Cette restriction
structurelle ne retire aucune lecture lexicale ou catégorie WordNet.

## Validations cumulatives des contraintes structurales — 21 octobre 2026

La cohorte expérimentale de 500 phrases reste figée (empreinte ci-dessus).
Les corrections de types de coordonnants, de causalité et d'apposition
font évoluer les statistiques **sans aucune augmentation arbitraire de score** :

- **Avant les nouvelles contraintes grammaticales** :
  455/500 avec le pruning lexical expérimental.
- **Après la licence positive de 36 coordinations non propositionnelles** :
  454/500. Les 19 usages erronés de `for` comme conjonction de NP/VP
  (18 phrases) sont éliminés des arbres sélectionnés. La seule analyse
  perdue (#427) utilisait `np_list_last` pour traiter `for Hands`
  comme élément d'une liste nominale : ce n'était pas une reconnaissance
  grammaticale valide.
- **Après la séparation du `for` causal fini et prépositionnel** :
  toujours 454/500, aucune perte, modification de six meilleurs arbres.
  `For my part` passe désormais par `PP` dans l'arbre #499;
  les propositions causales attestées restent disponibles.
- **Après la distinction pronominal/appositif** :
  toujours 454/500, aucune perte, deux meilleurs arbres modifiés.
  Les deux cas d'apposition avec un NP pronominal directement projeté
  (#95 et #482) disparaissent des arbres sélectionnés. Dans #482,
  `for the captain` est maintenant un `PP`, et `he` est
  distinctement le sujet de la proposition suivante.

Ces comptages mesurent une **précision locale des constructions**.
Ils ne démontrent pas une exactitude globale des 454 arbres. Les
faux rattachements restants des subordonnées et des groupes verbaux
sont encore documentés par les contre-exemples de tests.

Une expérience purement recherche
(`audit_unpunctuated_subordination.py`) a tenté de restreindre les
subordonnées antéposées sans virgule à une proposition matrice `NP VP`
finie. Sur 25 phrases contrastées, la couverture est descendue de 25
à 24, sans éliminer plusieurs analyses de constituants absurdes.
**Hypothèse rejetée pour intégration** : aucune règle de production
n'a été changée par cette expérience. Des preuves de frontières
propositionnelles et de valence plus fortes sont nécessaires.

## Diagnostic de la prochaine cause générale : frontières propositionnelles

L'inspection indépendante des **454 meilleurs arbres** expérimentaux
compte 21 occurrences de `clause_sub_front` dans 20 phrases distinctes.
Les signatures problématiques recouvrent notamment :

- **8 occurrences** dont la subordonnée a absorbé une virgule à
  l'intérieur de son propre constituant sans la laisser servir à la
  vraie frontière propositionnelle ;
- **3 occurrences** commençant par une subordonnée elliptique,
  parfois limitée à `he would` ou `eyes were` ;
- **1 occurrence** où la prétendue proposition principale est
  `up the vapours at a draught` analysée comme impératif.

Ces catégories se chevauchent et sont des **signaux** à contrôler
structurellement, pas autant de fautes certifiées. Le problème générique
semble être la certification insuffisante d'un sujet-prédicat fini
**complet**, combinée à des frontières de ponctuation sous-déterminées.
Un simple remplacement du second `CLAUSE` par `NP VP` a échoué
l'expérience contrastive. La piste suivante doit établir une interface
de clause attestée (valence, finitude, frontières, subordonnée versus
matrice), réutilisable à toutes les phrases, sans contournement de
`Parser.parse`.

Le [dernier test de la cohorte canonique](https://github.com/leye0/seman2/actions/runs/39600330696)
confirme 446/500 après ces restrictions grammaticales, soit la seule
ancienne analyse de `for Hands` rejetée par rapport au témoin
447/500. Aucun changement de complétion supplémentaire n'est constaté
après les restrictions causales et pronominales. Le corpus fixe et son
empreinte sont inchangés.

## Audit transversal des témoins de finitude (21 octobre 2026)

La proposition déclarative `clause_np_vp` ne demandait pas la preuve positive
`vform=finite` à son VP. Une première expérience grammaticale utilisant
`requires=[vform]` et `vform=finite` a produit **449/500** contre
**454/500** avec le même pruning lexical. Cinq phrases étaient perdues,
aucune récupérée. Une deuxième expérience a transmis `vform` à travers
les règles de VP récursifs (coordination, adverbiaux) : **454/500** contre
**454/500**, sans perte de couverture mais avec trois meilleurs arbres
modifiés. Le cas #365 (`traversed … and fixed on …`) est devenu moins
correct : le second verbe participe à une NP au lieu d'une coordination
de VP. **Ces modifications ne sont donc pas intégrées à la grammaire
canonique.** Les artefacts de comparaison sont associés aux expériences
[finie sans transmission](https://github.com/leye0/seman2/actions/runs/39605571538)
et [avec transmission](https://github.com/leye0/seman2/actions/runs/39606076608).

L'audit expérimental des 500 meilleurs arbres enregistre désormais des
signaux structurels, avec spans exacts et provenance des règles :
`unproven_declarative_vform` et `nonfinite_declarative_vp` sont
**distincts**, `mixed_vform_vp_coordination` inspecte les VP coordonnés,
`elliptical_front_subordinate` reconnaît les subordonnées elliptiques,
`imperative_matrix_after_subordinate` relève les matrices impératives,
et `internal_comma_in_front_subordinate` observe les virgules absorbées
par une subordonnée. Les compteurs de synthèse comptent les **phrases
distinctes**, pas les occurrences. Aucun de ces signaux n'est en lui-même
une preuve de faute grammaticale. La suite doit valider les classes de
signaux et corriger la valence et la transmission des traits à leur source.

## Résultats quantifiés de l'audit des traits morphosyntaxiques

[Exécution des 500 phrases](https://github.com/leye0/seman2/actions/runs/39607780390) :
454/500 reconnues avec le pruning expérimental, et cinq types
d'alertes distingués sur les meilleurs arbres. **26** phrases ont une
finitude de VP déclaratif non prouvée, **8** une virgule à l'intérieur
d'une subordonnée antéposée, **3** une subordonnée antéposée elliptique,
**2** une coordination VP avec `finite` et `ed` explicitement
incompatibles (#281, #365), et **1** une matrice impérative suspecte
après subordination (#485). Ce sont des signatures exploratoires, non
des erreurs grammaticales toutes certifiées.

Les deux coordinations opposant `vform=finite` et `vform=ed`
emploient `vp_part_pp` avec `vp_transitive`; le lexique et les
contraintes de valence doivent être inspectés avant d'imposer un
accord de forme entre les deux VP. Les expériences de contrainte
`vform=finite` ont précisément montré la nécessité de préserver les
branches grammaticales avant de modifier leur classement.

## Liaison WordNet–VerbNet des cadres de valence

La tâche de [traçage verbal](https://github.com/leye0/seman2/actions/runs/39609458515)
a confirmé la présence de **lectures `finite` et `ed`** de
`traversed`, `fixed`, `encompassed` et `drank` dans le treillis.
Les catégories ne sont donc pas à réduire. Le VerbNet 3.4 compilé
fournit dix cadres pour `fix`, mais aucun cadre `PREP:on` : des
cadres transitifs `NP`, `NP+PP` avec des prépositions sélectionnées,
et `ADV` sont présents. L'analyse littéraire `fixed on ...` nécessite
une valence non attestée **dans ce paquet VerbNet**; l'absence ici
ne démontre pas l'absence de la construction en anglais. La tâche
`audit_verbal_readings.py` relie désormais les lectures du treillis
à **tous les cadres VerbNet disponibles pour leur lemme**, en distinguant
une sélection `PREP` directe d'une séquence `NP+PREP+NP`.
La prochaine modification des règles de composition devra être fondée
sur les contraintes de ces cadres et sur des exemples contrastifs,
non sur une règle `V+PP` arbitrairement permissive.
