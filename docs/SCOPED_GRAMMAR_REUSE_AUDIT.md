# Audit de réutilisation des règles de composition

Base observée : [`91d942c`][base], après le lot 1 de Novel-1500. Le présent
audit ne modifie ni le parseur, ni la grammaire, ni les corpus. Il distingue
**répétition de forme**, **répétition d'opération grammaticale** et
**réutilisation mesurée sur les phrases du corpus**.

## Ce qui se répète réellement

La grammaire canonique contient 615 productions. La grammaire de composition
structurelle en contient 1 543, dont 1 387 associées à 376 valeurs distinctes
de `provenance.source_plan`. Ces valeurs sont des clés de portée et ne
correspondent pas toutes à une seule production ou à un seul patron Python.

| Rejeu figé | Passages complets | Racine sélectionnée avec `source_plan` | Plans sélectionnés distincts | Plans sélectionnés pour un seul passage |
| --- | ---: | ---: | ---: | ---: |
| Novel-1000 v3, sans les 30 témoins séparés | 1 000 | 354 | 332 | 323 |
| N1001–N1500 après le lot 1 | 401 | 13 | 13 | 13 |

Le comptage ne regarde que la racine choisie avec une provenance explicite.
Il ne compte ni les sous-règles, ni les plans essayés et non retenus. Il ne
classe pas non plus comme spécialisé le reste du moteur. Un plan utilisé une
seule fois sur cet échantillon n'est pas nécessairement applicable une seule
fois. En revanche, **ces rejeux n'apportent presque aucune preuve de réemploi
entre passages** pour les plans sélectionnés à ce jour.

Comparer seulement les catégories exactes du côté gauche et du côté droit
donne **12 formes présentes dans plusieurs portées**, sur 31 productions.
C'est une liste à examiner, pas une liste de doublons à supprimer. Par
exemple, `structural_nominal_with_perfect_object_relative` et
`structural_conditional_series_relative_topic` ont tous deux la forme
`NP → NP REL-CLAUSE-OBJ`. La première rattache un objet direct absent, la
seconde résout le complément d'une préposition laissée en fin de relative.
Les contraintes, les sorties et les rôles diffèrent.

Inversement, deux règles peuvent accomplir la même opération locale sans
partager les mêmes catégories. Le lot 1 réécrit la liaison d'une relative
avec les catégories `N1500-OBJECT-RELATIVE`, `N1500-INTERVAL-RELATIVE`,
`N1500-RECOVERY-RELATIVE` et `N1500-POSSESSIVE-RELATIVE`, entre autres.
Cinq plans écrivent chacun directement `RELATIVE_ANTECEDENT`. Ce dernier
nombre est un signal de répétition, pas un inventaire des relatives. Les
règles anciennes utilisent aussi, par exemple, `RELATIVE_REF`, des alias
d'argument, ou seulement `MODIFIER`.

## Le pattern manquant — liaison du rôle ouvert d'une relative à son antécédent

Nom proposé pour le contrat de composition : **`headed_relative_slot_binding`**.
Une relative à antécédent nominal laisse un rôle ouvert dans une prédication
ou dans un groupe nominal interne. La composition doit transmettre ce rôle
jusqu'au constituant où l'antécédent est choisi, puis le lier au bon nœud
source. Le choix de l'antécédent et la nature du rôle sont deux décisions
distinctes. Le contrat n'a pas besoin de connaître le verbe de la phrase
principale.

| Témoin | Rôle à transmettre | Ce que la règle ne doit pas faire |
| --- | --- | --- |
| N1010, le voyage vers Ingolstadt, qui était long et fatigant | Sujet de la prédication copulaire. L'antécédent est *journey*. | Faire de la destination l'antécédent ou généraliser « choisir le nom le plus proche ». |
| N1015, la santé qui ne s'était pas remise du choc subi | Sujet de *recovered* pour la relative externe. Objet direct de *sustained* pour la relative interne sans marqueur. | Lier *shock* à la mauvaise prédication ou remplacer le sujet explicite *it*. |
| N1006, la peine que tous ont ressentie et doivent ressentir | Objet direct partagé par *felt* et *feel*. *All* reste leur sujet explicite. | Traiter *which* comme sujet, ou attribuer l'objet absent à une coordination qui ne partage pas de lacune. |
| N1024, le démon dont la barbarie cause deux effets | Possesseur du sujet nominal *barbarity*, qui reste le sujet causal des deux prédicats. | Mettre *fiend* directement à la place de *barbarity* dans les prédicats. |
| N1050, relative introduite par *round which* | Argument de la préposition, pas objet direct de *towed*. | Considérer le passage comme corrigé. L'antécédent et les attaches doivent encore être vérifiés. |

La ponctuation et le marqueur font partie de la preuve, mais ne suffisent
pas. Une relative restrictive et une relative en supplément ne sont pas
interchangeables. Une relative avec `whose` transmet un rôle dans un groupe
nominal, une relative prépositionnelle transmet un rôle dans un SP, et une
relative libre constitue un cas distinct sans antécédent nominal externe.

### Preuve du défaut sur un exemple hors des patrons du lot 1

Avec WordNet 3.0 et le parcours `extract → parse_corpus_case`, employer
le même groupe nominal comme sujet puis comme objet donne le même défaut.

| Contrôle indépendant | Résultat observé |
| --- | --- |
| *The letter she had written arrived.* | Complet. `np_relative_obj → wh_bare_perfect_object_relative → vp_gap_perfect_transitive`. Le graphe produit `MODIFIER(letter, she)`, mais pas le lien d'objet entre *written* et *letter*. |
| *I found the letter she had written.* | Complet, même sous-arbre et même défaut de graphe. Le verbe principal et la fonction du groupe nominal ont changé. |
| *The letter which she had written arrived.* | Racine trouvée, aucune analyse valide sélectionnée. La forme avec *which* ne bénéficie pas du même parcours que la forme sans marqueur. |
| *The letter which had arrived was sealed.* | Complet avec `np_relative_subj`. Le graphe donne l'argument de *arrived* à *which* et ne le lie pas à *letter*. |

Le premier défaut est localisable. `vp_gap_perfect_transitive` représente
déjà la lacune d'objet. `wh_bare_perfect_object_relative` connaît le
prédicat lexical et le sujet, mais `np_relative_obj` demande le
`referent` générique de son enfant relatif pour le traiter comme
`relative`. Dans les deux contrôles, ce référent est celui du sujet
interne. `SemanticInterpreter._walk` hérite les handles génériques des
enfants dans leur ordre et le producteur de la relative ne les redéfinit
pas pour ce consommateur. Le problème n'est donc pas « il manque encore
une règle pour les lettres ». **La preuve de la lacune existe, mais le
parent ne l'utilise pas.**

## Contrat à essayer avant d'ajouter un patron de phrase

1. **La relative prouve et exporte ses emplacements d'argument.** Un
   emplacement précise son propriétaire réel — prédicat lexical, nom
   possédé ou préposition — et le rôle syntaxique encore ouvert. Il porte
   aussi les contraintes qui le rendent licite, par exemple la valence
   transitive et la forme participiale. Le marqueur et le sujet interne
   ont leurs propres sorties. En particulier, un auxiliaire ne remplace
   pas le prédicat lexical comme propriétaire de la lacune.
2. **Le rattachement nominal fournit la tête et ferme les emplacements
   compatibles.** Si deux têtes sont possibles, conserver les candidats
   justifiés et les départager avec les preuves disponibles. Le modifieur
   nominal et le lien du rôle rempli sont deux liens distincts.
3. **L'interprétation traduit le rôle syntaxique avec la valence et le
   sens sélectionnés.** Ne pas uniformiser tous les sujets en `AGENT` ou
   tous les objets en `PATIENT`. Les résultats ci-dessus prouvent des
   erreurs de liaison, pas qu'un nouveau nom d'arête devrait remplacer
   les catégories sémantiques existantes.
4. **La coordination réutilise la même liaison, sous preuve.** Pour
   N1006, l'antécédent remplit deux emplacements explicitement compatibles.
   Une branche qui a déjà son objet ne doit pas hériter un second objet.
   Une coordination de deux relatives, comme celle de N1150, n'est pas
   automatiquement une seule relative à sujet partagé.

Il existe déjà deux briques à réemployer : les traits `gap` et
`licensed_transitive` dans la grammaire, et les sorties explicites de
constituants utilisées par le compositeur. Aucun besoin démontré d'un
deuxième analyseur. Ce qui manque est un contrat commun entre le
producteur de la relative, le parent qui connaît sa tête et la projection
du graphe. Les portées existantes peuvent borner une première expérience
sans devenir le nom ou la définition du mécanisme.

## Ordre d'essai et preuve de transfert

- **Premier essai** : réutiliser le parfait transitif avec lacune d'objet
  pour une relative à sujet explicite avec ou sans marqueur. N1015 et les
  contrôles ci-dessus servent à diagnostiquer la jonction. Ajouter ensuite
  N1006 comme premier test de propagation dans une coordination prouvée.
  Garder les cas sujet, possessif, prépositionnel et libre comme contrastes
  séparés. Ne pas tenter de tout fusionner en une règle.
- **Transfert à mesurer** : réserver avant l'implémentation des passages
  réels qui n'ont pas servi au diagnostic. N1211, N1411, N1413 et N1417
  sont des candidats au criblage pour les relatives objets au parfait.
  Leurs échecs peuvent aussi venir d'un autre constituant. Ne pas les
  compter comme des gains avant le rejeu et l'inspection. Inclure des
  contrastes avec un objet déjà présent et un sujet interne différent de
  l'antécédent, puis vérifier aussi les rattachements réussis qui restent
  dans la cohorte.
- **Critère de progrès** : rapporter les sous-règles spécialisées remplacées
  par le contrat commun, les témoins nouveaux avec bon arbre **et** bon
  graphe, les changements de rang et les régressions éventuelles aux
  budgets constants. Une migration change légitimement des identifiants
  de règles sur les témoins visés. Comparer leurs spans, dépendances et
  rôles, tout en gardant les signatures exactes sur les cas non visés.
  Aucun plan entier n'est à supprimer avant d'avoir prouvé les autres
  relations qu'il protégeait.

Deux familles viennent ensuite. **Le partage de sujet entre prédicats
coordonnés** apparaît dans N1012, N1014, N1024, N1025 et N1041, mais le
partage syntaxique n'implique pas un même rôle sémantique. *Dance* est agent
de *dismounted* et patient de *admitted*. **L'attribution d'un tour cité
interrompu** apparaît dans N1037 et N1039. On peut partager le mécanisme
d'attribution au même rapporteur, pas la résolution de la négation ou du
contenu elliptique. Les 106 portées qui écrivent directement `CONJUNCT` et
les 70 qui écrivent `REPORTED_CONTENT` sont des pistes de recherche, pas
des preuves qu'elles implémentent toutes un même mécanisme.

## Reproduire l'inventaire

À la racine, fournir les dossiers contenant les fichiers `novel-*-parses.jsonl`
émis par [le rejeu v3][v3] et [le rejeu Novel-1500][n1500], ou construits avec
les commandes de rejeu de la branche. Le nom du groupe 1030 correspond aux
30 témoins séparés.

```sh
export PYTHONPATH=superparser
python -m scripts.audit_scoped_rule_reuse \
  --replay-dir /tmp/novel1000-parent --replay-dir /tmp/novel1500-replay \
  --exclude-replay-file novel-1030-parses.jsonl
python -m unittest -q superparser.tests.test_audit_scoped_rule_reuse
```

Sans dossiers de rejeu, la commande produit l'inventaire statique. Elle lit
directement les recettes déclaratives et ne modifie aucun fichier de grammaire.
L'audit d'identité stricte de productions demeure distinct, dans
[`audit_equivalent_rules.py`](../superparser/scripts/audit_equivalent_rules.py).

[base]: https://github.com/leye0/seman2/commit/91d942c15a7ff3de7516b83ae29a0299842ef9d9
[v3]: NOVEL1000_REPORTING_V3.md
[n1500]: NOVEL1500_EXPLORATION.md
