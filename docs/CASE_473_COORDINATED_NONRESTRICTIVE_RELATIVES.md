# Cas 473 — deux relatives coordonnees, lacune d'objet et infinitive nominale

## Cohorte et diagnostic

- Revision `main` de depart : `e9225faa1d808b6d66a78f2529bd0192415ec1e0`.
- Cohorte strictement gelee : SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a` ; index **473**, *Treasure Island* (Gutenberg 120).
- Phrase originale et analyse `QUOTE_BALANCED` : `the rest were revenue officers, whom he had met by the way, and with whom he had had the intelligence to return at once.` (aucun guillemet synthetique ajoute a ce cas).
- Budget inchange : `max_items=50000`, `kbest_work_limit=500000`, WordNet 3.0.
- Base : `completed=false`, `roots_without_valid_analysis`, `forest_nodes=836`, `partial_states=30952` ; bilan strict **474/500** avant correction.

Le cas combine un nom compose dont le nom tete est pluriel (`revenue officers`), une expression anaphorique (`the rest were`), une relative avec lacune d'objet et PP adjoint (`whom he had met by the way`), puis une seconde relative pied-pipee en PP (`with whom he had had the intelligence to return at once`). La seconde relative contient un objet nominal avec postmodificateur infinitif : **`to return at once` modifie `the intelligence`**, pas le verbe copule `were`.

Une premiere regle monolithique `NP COMMA REL-OBJ COMMA COORD REL-PP` rendait la cible complete, mais degradait le temoin de saturation 359 et selectionnait initialement le mauvais rattachement infinitif. Cette variante a ete **abandonnee**, tout comme un `VP-GAP` global trop expansif. La solution livree factorise la coordination dans une structure relative, et reutilise la projection nominale preexistante.

## Construction factorisee, sans reconnaissance de la phrase

1. `n_compound` construit `N` a partir d'un **modificateur nominal singulier** et d'un nom tete de nombre independant. Le nombre du compose provient seulement du tete : `revenue officers`, `coffee traders`, `school buses`. La contrainte sur le modificateur empeche d'inventer le compose `likes coffee` pour accepter `He does not likes coffee.`. Le lattice marque generiquement les candidats `N` dont la **meme surface possede aussi une lecture `DET`** : ces candidats restent presents, mais ne peuvent pas servir de modificateur nominal dans `n_compound`. Cela empeche de reparcourir `a heavy gales` comme un groupe nominal de noms composes, tout en autorisant `school bus driver`. Aucun lexeme n'est enumere dans ce traitement.
2. Le lexique conserve l'entree WordNet de `rest` et ajoute une lecture **anaphorique collective plurielle** pour les restes d'un ensemble comptable (`the rest were ...`). C'est une polysemie de **nom**, pas un raccourci sur cette phrase ; la lecture singuliere (`the rest was water`) reste active. Aucun mot comme `revenue`, `officers`, `met`, `intelligence` ou sequence de la phrase n'est ajoute comme declencheur de regle grammaticale.
3. `rel_obj_overt_wh_perfect_gap_with_pp` construit une relative d'objet a partir de `WH-REL-OBL + NP sujet + HAVE fini + V participe transitif + PP`. Le sujet impose l'accord avec l'auxiliaire ; le verbe doit etre **transitif**, l'objet est la lacune du pronom relatif, et le PP demeure un adjoint. La regle ne fabrique aucun `VP-GAP` sans relatif overt.
4. `rel_pp_coordinated_with_object_relative` coordonne une `REL-CLAUSE-OBJ` et une `REL-CLAUSE-PP` uniquement avec une **vraie virgule** et un coordinateur nominal. La structure conserve les deux enfants, leurs lacunes `object` et `pp` et les evenements distincts ; son interface externe herite du type PP du membre droit pour reutiliser `np_relative_pp_comma`.
5. `np_relative_pp_comma` / `np_relative_pp_comma_pair` propagent le marqueur `supplementary_relatives=true` et exigent des **virgules litterales** ; un point final n'est plus confondu avec une virgule de fermeture. `np_inf_rel` et `vp_cop_np_inf` ne peuvent pas placer une infinitive **au-dela** d'une relative supplementary deja rattachee. L'infinitive reste ainsi dans l'objet nominal de la seconde relative.

## Arbre de rang 1 attendu

| Segment de la phrase | Regle | Relation grammaticale |
| --- | --- | --- |
| `the rest were ...` | `clause_np_vp` et `vp_cop_np` | Sujet pluriel anaphorique, copule `were`, attribut nominal complet. |
| `revenue officers` | `np_bare` et `n_compound` | `officers` est la tete plurielle, `revenue` un modificateur nominal singulier. |
| `revenue officers, whom ... and with whom ...` | `np_relative_pp_comma` | **Un seul** antecedent nominal, suivi d'un groupe de relatives. |
| `whom he had met by the way` | `rel_obj_overt_wh_perfect_gap_with_pp` | `whom` represente l'objet manquant du transitif `met` ; `by the way` est un PP adjoint. |
| `, and` entre les relatives | `rel_pp_coordinated_with_object_relative` | Virgule litterale, coordination de deux relatives, pas de deux groupes nominaux. |
| `with whom he had had ...` | `rel_pp_finite_np_vp` et `vp_perfect_trans` | PP relatif pied-pipe, sujet `he`, parfait `had had`. |
| `the intelligence to return at once` | `np_inf_rel` | `to return at once` reste **dans** l'objet nominal de `had had` ; jamais une extraposition de `were`. |

Les tests verifient la **position et les parents** des noeuds, pas seulement `completed=true` ; la terminaison `.` est exclue de la virgule de fermeture du groupe nominal.

## Controles

- Nouveaux tests : `superparser/tests/test_coordinated_supplementary_relatives.py` ; positifs independants avec `teachers` et `coffee traders`, contraste singulier/pluriel de `rest`, negatifs de sujet singulier avec copule plurielle et de faux trou d'objet avec `slept`, controle `school bus driver` et rejet `a heavy gales` au niveau nominal.
- Temoins exacts : 359 garde `dialogue_unattributed` et **1472** noeuds de foret, **48529** etats partiels, malgre sa saturation historique deja presente.
- Smoke Layer 1 : **PASS**.
- Qualite directe : **120/120** annotations, **24/24** contrastes, **9/24** faux positifs negatifs deja connus. Le contre-exemple nouveau `He does not likes coffee.` detecte dans une iteration a ete corrige avant validation.
- Comparaison exhaustive **500 cas** a SHA identique, budgets et `QUOTE_BALANCED` identiques : bilan strict **474/500 -> 474/500**. Deux changements exactement : **473** passe de `roots_without_valid_analysis` a `complete`, et **466** passe de `complete` a `roots_without_valid_analysis`. Aucune modification des indicateurs de saturation ou de delai pour les 500 indices. Les **25 autres cas non complets** de la base conservent leur statut.

### Pourquoi le total n'augmente pas encore : ancien faux positif 466

Le temoin 466 est `"Ah, well, my son, you praise your stars he's dead," said Silver.`. Son ancien arbre de rang 1 etait **incorrect** : le groupe `your stars he's dead` etait analyse comme `np_genitive`, avec `np_poss` portant le nom compose absurde `stars he`, et `'s dead` comme possessif suivi du nom `dead`. Le nombre du nom compose rendu compatible par l'ancienne grammaire avait masque l'absence d'un vrai traitement de la proposition finie juxtaposee `he's dead`. Il serait contraire a l'exigence d'attaches exactes de conserver cette analyse pour afficher 475/500. Il faudra traiter **separement** la structure de discours ou de completive non introduite en 466, sans retablir cette analyse nominale factice ni supposer que la formulation litteraire est necessairement une erreur.

- Suite exhaustive locale : **500 tests, 500 reussis** ; tests cibles de 473 et temoin 359 inclus. CI : a renseigner apres validation distante.

La grammaire ne contient aucun identifiant de cas ni test de surface exact. La lecture lexicale de `rest` est explicite et documentee, et peut etre evaluee independamment de la phrase cible. Les **modificateurs nominaux pluriels lexicalises** ne sont pas generalises arbitrairement par cette regle : leur statut demande une preuve de selection distincte avant d'elargir le domaine, pour ne pas recreer les faux positifs.
