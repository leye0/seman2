# Novel-1000 — première factorisation des règles

Base de comparaison strictement épinglée : `6bec2b3`. La conception et
les contrastes viennent de [l'inventaire Novel-1000](NOVEL1000_GENERALIZABLE_PATTERNS.md).
La recherche, le classement, les éditions des livres, le découpage et
les budgets n'ont pas été élargis.

## Des règles en moins

Six productions canoniques avaient les mêmes catégories, contraintes,
exports, exigences positives et actions après renommage de leurs
variables locales. Le score était inférieur ou égal à celui de la
production conservée. On garde la production qui dominait déjà ou, en
cas d'égalité, la première dans la grammaire.

| Conservée | Supprimée |
| --- | --- |
| `vp_perfect` | `vp_perfect_intrans` |
| `vp_passive_inf` | `vp_raising_passive` |
| `vp_cop_np_comma_neg` | `vp_cop_np_neg` |
| `vp_that_modal_adv` | `vp_that_modal_vp_adv` |
| `vp_that_npcoord_vp_adv` | `vp_that_np_vp_adv` |
| `vp_colon_question` | `vp_comma_clause` |

Les IDs historiques laissés en place ne décrivent pas toujours exactement
la portée de la production. Les renommer dans cette passe aurait changé
des signatures et brouillé la comparaison. Aucun ID supprimé n'était
sélectionné au rang 1 dans les 1 030 entrées. Le rejeu de l'ablation seule
préserve tous les arbres et graphes épinglés. Le nouvel inventaire compte
609 productions canoniques, contre 615, et ne trouve plus de doublons au
sens étroit de cette comparaison, en incluant les exigences et portées.
Il ne déclare pas équivalentes des règles ayant seulement le même côté droit.
Dans un contrôle des alternatives (limite de 24 sur 16 passages), comparer
les structures après réassociation des anciens IDs n'a montré aucune
alternative unique perdue. Cinq passages ont libéré de la place pour
huit alternatives distinctes dans cette fenêtre.

## Énoncer une relation une fois

Une recette avec plusieurs sources ou plusieurs cibles peut écrire une
seule relation avec `sources` **ou** `targets`. La mise en forme est
abaissée en arêtes ordinaires et ordonnées au chargement, avec leurs
conditions inchangées. Il n'y a ni produit cartésien ni propagation
implicite. Par exemple, un groupe de prédicats qui porte déjà le même
argument sous la même étiquette peut déclarer toutes ses ancres ensemble.

**215 répétitions de déclaration ont été supprimées dans 154 recettes**.
Les 1 321 recettes de dialogue compilées restent identiques. Le même test
d'égalité tient pour les recettes canoniques hors de la migration de
liaison décrite ci-dessous et des six doublons.

## Une liaison commune, des preuves différentes

L'export d'un groupe d'arguments repose sur le sous-arbre retenu. Il
indique le rôle ouvert, les ancres lexicales qui le réclament et leurs
contraintes d'accord. Le groupe ne franchit pas les nœuds intermédiaires
par héritage de `referent`. Au consommateur, un groupe nominal attesté
fournit son référent et le lien est émis aux ancres vérifiées. Ni le
groupe ni le référent ne peuvent provenir d'une devinette au niveau du
graphe.

- **Coordination**. Les deux variantes canoniques et la liste à trois
  membres peuvent exporter le même groupe de sujets. Chaque VP doit
  prouver sa finitude indépendante et sa voix active. Un auxiliaire
  attesté de parfait ou de progressif, ou un modal attesté, peut porter
  la finitude. C'est le prédicat lexical qui possède le sujet. Le cas de
  *Jane went …, kissed …, and thanked …* garde le premier prédicat comme
  tête de la coordination et ne reçoit pas une deuxième topologie.
- **Relative sujet restrictive**. Une marque attestée (*who*, *which*,
  *that*) et un prédicat compatible exportent une position de sujet.
  Le nom tête simple non pronominal la lie, avec une relation séparée entre marqueur et
  antécédent. Dans *the load that weighed upon my mind*, *load* reste
  l'objet du verbe extérieur et devient aussi sujet de *weighed*.

Dans les deux routes, la projection est syntaxique (`SUBJECT`). On ne
propage pas `AGENT` ni une autre étiquette sémantique de la branche
voisine. Les anciennes arêtes du graphe ne sont pas écrasées. La règle
s'abstient notamment devant une voix passive, une relative objet ou PP,
un antécédent complexe, un contrôle infinitival, un verbe de forme
non fléchie sans porteur fini indépendant ou une coordination interne
dont on ne sait pas prouver toutes les branches. Elle ne confond pas
point-virgule et virgule, ni la tête d'un nom propre avec un titre
incomplet. Pour la relative, une tête candidate homographe d'un
auxiliaire de l'inventaire fermé est laissée en suspens si aucun
porteur distinct n'établit l'analyse. Ces contrôles ne résolvent pas
un mauvais rattachement de rang 1.

## Preuves et limites

Sur les **1 000 passages v3 et les 30 témoins**, le rang 1 et les drapeaux
de budget sont identiques. Les graphes de **17 passages** reçoivent
uniquement **38 arêtes relues**. Ce sont 33 liens de sujet, deux liens
marqueur–antécédent et trois liens de coordination. Aucun des 30 graphes
témoins ne change. Les nœuds, les handles et toutes les anciennes arêtes
gardent leur ordre et leur identité. Cette comparaison ne certifie pas
toute l'analyse sémantique des 17 graphes.

Le rejeu de l'extension Novel-1500, séparé de la découverte des motifs,
a servi à écarter des extrapolations trop larges avant de fixer cette
version. Après resserrement, **401/500** passages restent complets avec
les mêmes arbres, et 12 graphes reçoivent des liens locaux. Ce n'est
pas un test aveugle après cette vérification. Aucun nouveau patron ne
vient de l'extension. La catégorie de limite signalée pour un passage
déjà incomplet (N1320) varie entre rejeux, et un drapeau de forêt
héréditaire disparaît dans ce rejeu de N1247. Ni l'un ni l'autre
n'est compté comme un gain de couverture.

L'ablation en mémoire du composeur spécialisé de sujets partagés
(`structural_shared_subject_source_sentence`) n'a terminé aucun des six
passages où ce composeur gagne. Par exemple, Q3-373 doit conserver la
subordonnée en *when* à l'intérieur du premier prédicat et retrouver la
seconde branche après elle. Supprimer les patrons entiers aurait retiré
cette reconnaissance. Ils restent en place. Une future migration peut
factoriser la preuve d'un supplément borné sans assimiler ses sujets
internes au groupe extérieur.

Les échecs de validation provenant de la sélection historique d'un cas
par index ne sont pas une preuve contre la factorisation. Ne pas changer
le corpus ou repinner un ancien score pour les faire disparaître. Les
contrôles de cette passe reconstruisent les cas v3 par leurs ancres,
et non par la numérotation d'un autre échantillonnage.

## Rejouer le contrôle

La [liste des arêtes relues](../superparser/research/novel1000_generalization/reviewed-graph-deltas.json)
conserve la SHA de chaque source, la signature du graphe révisé et les spans exacts. Le contrôleur refuse
toute autre modification, même si les 1 030 passages demeurent complets.
Le script peut afficher un diff pour la relecture avec `--inspect`, ce qui
ne valide ni ne repinne la liste. Le workflow de la branche reconstruit les
deux rejeux.

```sh
export PYTHONPATH=superparser
python -m scripts.audit_equivalent_rules --inventory-only
python -m scripts.novel_source_reporting_v3 replay --group all \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel1000-after
python -m scripts.compare_novel1000_semantic_replay \
  --baseline /tmp/novel1000-before --candidate /tmp/novel1000-after
```

`/tmp/novel1000-before` doit être un rejeu de la base épinglée ci-dessus.
Le contrôle historique `novel_source_reporting_v3 check` continue d'exiger
les graphes v3 originaux. C'est le nouveau comparateur qui accepte
uniquement les arêtes revues de la migration.
