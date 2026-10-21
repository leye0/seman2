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
