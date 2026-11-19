# Composer les règles sans réécrire la phrase

**La quantité de règles ajoutées pour un nouveau corpus est le problème
à mesurer.** Un score obtenu après réparation des cas de ce corpus
mesure la couverture de cette version, pas son transfert.

## Pourquoi les patrons se multiplient

Sur le point de départ `25016d9`, 354 passages sur 1 000 sélectionnent
une racine à portée explicite. Ces racines font appel à 332 plans
distincts, dont 323 ne sont sélectionnés que pour un seul passage de
l'échantillon. Ce comptage porte sur la racine et non toutes les
sous-règles. Il ne prétend pas que 323 plans sont des doublons.

Une ablation de l'ensemble du dispatch source sur les 500 passages de
l'extension, avec la même grammaire canonique, le même corpus et les
mêmes plafonds, fait passer la complétion de 409 à 391. Dix autres
passages restent complets avec une analyse ou un graphe différent.
Retirer les patrons d'un coup perd donc du travail sans résoudre le
problème. Ces chiffres ne donnent ni la part des échecs due au dispatch
ni la qualité des analyses de remplacement.

Le mécanisme est visible dans `_compose_verified_dialogue_pattern`.
Le plan choisit au préalable les coupures, les catégories et souvent
l'identifiant de l'analyse enfant à accepter. Le moteur analyse chaque
morceau, puis le plan vérifie son meilleur résultat local. Le plan
réencode ainsi à la fois la grammaire du morceau, ses contraintes et
la façon de raccorder ses voisins. Modifier une seule dimension d'un
exemple peut demander un nouveau plan de la phrase entière, même si
chaque opération prise isolément existe déjà.

À la frontière entre deux constituants, le moteur répétait ce défaut.
Il utilisait les traits du meilleur résultat enfant pour borner et
parfois éliminer tout ce que cet enfant pouvait fournir. S'il rejetait
un rang lors de l'unification, il ne réclamait pas les rangs suivants.
De plus, le nombre de résultats à afficher limitait les analyses que
le parent pouvait demander. Le même ensemble de règles pouvait donc
fonctionner sur la chaîne entière et échouer après composition.

## Premier changement au moteur

Le parent reçoit un flux de preuves avec leurs traits et leurs spans,
pas une décision locale définitive. La même unification et les mêmes
exigences de preuve positive s'appliquent à chaque candidat. Si un
candidat ne convient pas, le rang suivant reste disponible. Il est
examiné à la demande sous les plafonds existants. La vue publique
`k-best` reste une limite d'affichage, non un filtre grammatical. Un
budget épuisé ne devient jamais une analyse acceptée.

L'inspection des productions effectivement reconnues élimine une
demande impossible avant le classement. Par exemple, une règle
qui exige que le groupe verbal atteste un complément de moyen ne
doit pas parcourir des milliers de lectures d'un groupe verbal dont
aucune règle reconnue n'exporte ce trait. Ce filtre n'utilise pas la
lecture locale préférée et n'efface aucune alternative admissible.

Les tests rendent ambigus à la fois le nombre et la forme verbale, puis
comparent l'analyse à plat à celle qui passe par un constituant. Ils
vérifient aussi les identités d'ancres et les portées avec la grammaire
anglaise existante. Isoler *read* ne doit pas faire échouer son réemploi
dans *They can read the book*, *They want to read the book*, *He did read
the book* ou à l'impératif. Ici, aucune règle grammaticale, recette
sémantique ou entrée lexicale n'est ajoutée.

## Ce que cette brique ne règle pas encore

Réessayer les preuves enfant n'apprend pas au moteur où proposer une
frontière, ne crée pas une valence manquante et ne résout pas un
rattachement ambigu. Les plans historiques qui exigent un
`proof_rule` au rang 1 ne sont pas convertis par ce changement.
L'ordre de recherche interne et les traits exportés limitent aussi
l'équivalence entre les parcours à plat et composés.

Le prochain changement architectural est de remplacer, par famille,
ces plans qui prescrivent un arbre par des contrats entre constituants.
Un prédicat offre ses arguments et ses emplacements encore ouverts.
Le parent exige un rôle et des traits, et la preuve de liaison indique
quel nœud source remplit le rôle. La ponctuation et la préanalyse
doivent proposer des bornes compatibles, sans décider le rôle à la
place de la grammaire. Un plan existant ne peut être retiré que lorsque
ses rattachements sont réellement récupérés.

Pour vérifier un transfert, figer les règles avant de lire un lot
inédit. Mesurer alors séparément la complétion sans nouveaux plans,
la justesse des rattachements au rang 1 sur un échantillon annoté et
les saturations aux budgets inchangés. Sur les lots déjà vus, comparer
aussi le nombre de plans retirés et le nombre de phrases qui en
dépendent encore. L'objectif est de faire baisser le coût du lot
suivant, pas de déplacer les mêmes cas particuliers vers un autre fichier.
