# Protocole

## Matière

Le corpus synthétique comprend :

- un motif atomique profond de six nœuds avec deux variables ;
- trois contextes intermédiaires réutilisant ce motif ;
- six contextes supérieurs réutilisant les composants intermédiaires ;
- 400 lexicalisations d'entraînement par contexte supérieur, soit 2 400 ;
- 100 lexicalisations inédites par contexte, soit 600 held-out.

La profondeur réelle vaut trois définitions : atomique, composée intermédiaire,
puis composée supérieure. Il y a donc deux niveaux d'appels.

## Représentations comparées

- **Plate** : six gabarits supérieurs entièrement développés.
- **Récursive** : une définition atomique, trois coquilles intermédiaires et
  six coquilles supérieures. Chaque dépendance partagée est payée une fois.

Les deux modèles utilisent le code logique POC-03. Les instances paient le
même sélecteur et toutes leurs variables. Le benchmark n'accorde donc aucun
rabais artificiel à une référence de composant.

## Invariants

1. Chaque snapshot reconstruit est identique à sa source.
2. Un mapping répété vers la même variable externe impose l'égalité.
3. Deux variables externes différentes ne sont pas forcées à être distinctes.
4. Les appels couvrent exactement toutes les variables de la dépendance.
5. Un port ne reçoit qu'un appel.
6. L'expansion et le matching interrompent toute récursion cyclique.
7. Le contenu canonique ne dépend ni des noms de variables ni de l'ordre des
   appels.
8. Un composant à support un reste une proposition non promue.
9. Une profondeur supérieure à huit est refusée par la politique v0.1.
10. Le rechargement persistant conserve les identifiants et expansions.

## Seuils préenregistrés

- reconstruction entraînement et held-out : 100 % ;
- profondeur minimale : 3 ;
- coût total récursif inférieur au coût total plat sur entraînement ;
- aucun gain held-out minimal exigé face au modèle plat déjà gelé ;
- rejet des cycles et des assemblages à support un.
