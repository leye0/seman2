# Seman2 — Consolidation grammaticale directe, une seule passe

Date : 17 octobre 2026. Travail expérimental sur `research/verbnet-left-to-right-poc`. **`main` non modifiée.**

## Décision architecturale

Nous **ne conservons pas de surcouche de correction** pour le parseur grammatical. Les corrections ont été appliquées directement aux deux emplacements responsables :

- `superparser/data/grammar.jsonl` : 82 productions VP transportent désormais le nombre/la personne de leur tête verbale lorsqu'elles ont une forme finie ou variable ; les constructions modales et auxiliaires négatives sélectionnent les compléments verbaux de base `VP-NP` ; `vp_obj_pred` réclame une véritable valence complexe ; `np_quant_n` impose l'accord du déterminant et du nom.
- `superparser/seman_parser/segmentation.py` : les formes du verbe *be* reçoivent leurs traits propres à la surface, sans propager des traits contradictoires des autres formes du même paradigme ; la troisième personne singulière productive en *-s* donne un accord lexical attesté ; `do` au présent/base n'est pas attribué à `does` ou `did` comme si ces formes étaient identiques.

Le code existant d'unification et le chart vectoriel restent l'autorité grammaticale : **nous n'avons pas modifié le moteur pour compenser une grammaire incomplète**.

La surcouche d'essai `grammar_consolidation.py` de la phase diagnostic a été abandonnée; ces nouvelles règles s'appliquent directement par `ParserResources.from_dir`.

## Comparaison globale reproductible

Workflow **VERT** : https://github.com/leye0/seman2/actions/runs/39044387477

Exécute le vrai `Parser` vectoriel, WordNet 3.0, 120 phrases annotées et les 24 paires agrammaticales/correctes. Le critère annoté reste le **meilleur arbre** sélectionné (non l'ensemble de la forêt) et les assertions ne constituent pas un gold tree complet.

| Mesure | Référence historique avant consolidation | Direct après consolidation |
|---|---:|---:|
| Phrases ayant un arbre complet | 120/120 | **120/120** |
| Assertions syntaxiques sur le meilleur arbre | 115/120 | **113/120** |
| Phrases volontairement incorrectes quand même reconnues | 19/24 | **10/24** |
| Contrastes grammaticaux corrects reconnus | 22/24 | **22/24** |
| Export syntaxique complet | 120/120 | **120/120** |
| Durée médiane comparée | Ne pas comparer entre runners | 7,1 ms |
| Durée p95 | Ne pas comparer entre runners | 25,5 ms |
| Cas au-delà des 500 ms de recherche | Non mesuré selon même protocole | **1/120** |

Le travail élimine donc **9 fausses acceptations** sur 24 (47 % relativement au nombre initial) sans perte de complétion ni des contrastes corrects. Cela **ne constitue pas une grammaire entièrement correcte**.

### Répartition des 10 négatives encore acceptées

- Accord : 3/8 ; modal : 3/5 ; auxiliaires : **0/4** ; déterminants : 1/2 ; valence : 3/5.

### Pourquoi 113 au lieu de 115 ?

Sur les nouvelles phrases présentant des échecs d'assertions, `d013` (« She can read the letter ») et `v013` (« They might solve the puzzle ») échouent uniquement au test `required_rules = ["vp_modal"]`. L'analyse principale reste complète, mais le chemin `VP-NP` est maintenant typiquement représenté par `vp_modal_bare`, une autre règle ancienne, déjà existante, à score plus élevé. Nous **n'avons pas abaissé le score de cette dernière juste pour faire passer l'assertion de nom de règle**. Les cinq autres cas correspondent à des échecs d'assertions déjà présents auparavant. Ce changement doit être vérifié au niveau sémantique/lexical avant de mettre à jour une annotation conventionnelle.

### Protection contre de futures dérives

`superparser/scripts/validate_direct_grammar.py` contient un contrôle CI **global**, sans exceptions sentence par sentence. Il échoue désormais si : les arbres complets ou les exports disparaissent, les assertions passent sous 113, les négatives acceptées remontent au-dessus de 10, ou les contrastes corrects descendent sous 22. Ce sont les seuils d'une **référence de travail**, pas des objectifs finals.

Les 12 tests de régression du parser hybride et du matcher C sont restés verts.

## Arrêt volontaire de cette passe

L'objectif convenu était un **diagnostic transversal + une intervention structurale + une validation globale**. Les trois étapes ont été effectuées. Ne pas ouvrir immédiatement une série de 10 corrections locales pour faire disparaître les 10 négatives restantes.

Les principales limites désormais connues :
- les formes verbales non marquées et les personnes des pronoms ne sont pas encore prouvées partout ;
- certains compléments prépositionnels exigent de conserver la préposition particulière du cadre lexical (ex. `depends on`), pas uniquement une catégorie `PP` ;
- une ambiguïté lexicale vraie ne doit jamais être supprimée pour forcer un test négatif ;
- un cas sur 120 dépasse la fenêtre exploratoire de 500 ms ; le nouveau script **observe** ce dépassement sans imposer de coupure, et il faut le surveiller plus tard.

**Prochaine étape prioritaire** : revenir à l'hybride C + forêt vectorielle et mesurer la réutilisation effective de structures dans le chart sur des textes d'auteurs inédits. Ne pas oublier que le résultat final doit être un `ParseResult` complet avec NP/VP/PP, fonctions, traits et alternative syntaxiques.
