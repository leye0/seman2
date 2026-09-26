# Verdict NLP-03

## Verdict

**GO** pour récupérer, identifier et conserver les analyses syntaxico-
sémantiques concurrentes produites par ACE/ERG.

**GO** pour énumérer les lectures de portée du cas contrôlé : l'adaptateur Z3
développé dans la POC transforme les contraintes MRS en candidats explicites,
sans choisir entre eux.

L'adaptateur est un prototype à intégrer et durcir pour la production, mais la
POC couvre désormais toutes les données demandées par NLP-03.

## Résultats observés

Avec `--max-results 25`, ACE retourne :

- 3 analyses pour l'ambiguïté d'attachement ;
- 8 analyses pour l'ambiguïté structurelle ;
- 3 analyses de parsing pour la phrase à portée ambiguë ;
- 5 analyses pour la phrase à trois quantificateurs.

Les 19 candidats sont tous conservés avec leur rang, score, MRS, arbre,
dérivation, qualité, support source et identifiant reproductible. Dix-huit MRS
sont bien formées ; deux candidats utilisent le prédicat de repli `unknown`.

Le solveur Z3 produit 34 solutions de portée au total. Pour la première phrase,
il en produit deux depuis l'analyse canonique et deux depuis l'analyse de repli
encore bien formée ; il refuse la troisième analyse, dont la MRS viole
l'unicité des variables intrinsèques. Pour la phrase à trois quantificateurs,
il produit six solutions pour chacune des cinq analyses ACE.

## Ce que signifie « toutes les analyses »

La POC conserve toutes les analyses **rendues dans la limite configurée**. Si
`limit_reached` vaut `true`, elle ne prétend pas connaître leur nombre total.
Le rang est une préférence fournie par ACE, pas une vérité et pas une identité.

Deux candidats peuvent avoir le même inventaire de prédicats tout en différant
par leurs relations, leur arbre ou leur dérivation. C'est notamment le cas des
attachements du groupe prépositionnel. La comparaison ne se limite donc jamais
à une liste de mots ou de prédicats.

## Résolution de portée

Pour **“Every dog chased a cat”**, la première analyse contient deux
quantificateurs et les contraintes `qeq` attendues. Cette MRS laisse ouvertes
au moins les lectures suivantes :

- chaque chien a pu poursuivre un chat différent ;
- un même chat a été poursuivi par tous les chiens.

Les trois résultats ACE ne correspondent pas à trois solutions de portée. Le
premier est l'analyse normale ; les deux suivants sont des analyses de repli
avec `unknown`, dont une MRS malformée. PyDelphin 1.11.0 sait tester la
plausibilité de la portée, mais l'API installée n'énumère pas les solutions.
L'adaptateur de la POC passe donc les holes, labels, `HCONS`, `RSTR` et `BODY`
à Z3.

Pour l'analyse canonique, Z3 retourne exactement :

```text
_every_q > _a_q
_a_q > _every_q
```

La première solution branche le `BODY` de `_every_q` vers `_a_q`, puis celui de
`_a_q` vers le prédicat de poursuite. La seconde effectue l'ordre inverse. Les
deux restrictions nominales restent liées directement à `_dog_n_1` et
`_cat_n_1`.

Pour **“Every student gave a teacher a book”**, les quantificateurs sont
identifiés avec leur restriction afin de distinguer les deux `_a_q`. Les six
ordres possibles sont obtenus, y compris ceux où l'étudiant, l'enseignant ou le
livre a la portée la plus large.

## Données fournies par chaque solution

Chaque solution fournit :

- un identifiant stable ;
- les bindings de handles et l'ordre de portée ;
- le graphe de dominance et la profondeur des labels ;
- chaque contrainte `qeq` satisfaite avec son chemin de labels justificatif ;
- un lien vers la MRS et l'analyse ACE sources ;
- une indication de troncature et les solutions de même ordre éventuelles ;
- la liste des alternatives incompatibles, sans `argmax` destructif.

Les MRS malformées, contraintes autres que `qeq`, bindings quantificationnels
ambigus et topologies non arborescentes ne sont pas approximés : le solveur
retourne un statut `invalid_source_mrs` ou `unsupported_*`. Cette frontière est
explicite et testable.

Z3 5.1.0 était déjà installé et fixé dans `requirements-cognitive.txt`. Aucune
nouvelle bibliothèque n'est nécessaire.

## Exemples linguistiques concrets

### Attachement

**“Kim saw the man with the telescope.”** peut signifier que Kim utilise le
télescope pour voir, ou que l'homme possède le télescope. ACE produit des
analyses distinctes où `_with_p` dépend de structures différentes. La POC les
conserve séparément même lorsque leurs prédicats sont identiques.

### Structure

**“Flying planes can be dangerous.”** peut parler de l'activité consistant à
piloter des avions, ou d'avions actuellement en vol. Les analyses diffèrent par
leurs prédicats, leurs nominalisations, leurs arbres et leurs règles de
dérivation ; ces différences sont toutes exposées.

### Portée

**“Every dog chased a cat.”** reçoit maintenant deux solutions explicites. La
première correspond à un chat potentiellement différent par chien ; la seconde
à un même chat pour tous. Elles restent simultanément disponibles et reliées à
la même MRS sous-spécifiée.
