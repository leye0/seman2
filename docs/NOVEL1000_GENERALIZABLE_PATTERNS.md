# Novel-1000 — motifs de composition à factoriser

Cet audit prend Novel-1000 v3 comme corpus de travail. Il analyse le rejeu
canonique de **1 000 passages**, chacun avec son arbre de rang 1 et son graphe.
Les groupes, les sources, les signatures et les budgets doivent correspondre
aux épingles v3. Les 30 témoins dialogue sont rejoués pour la vérification,
mais ne comptent dans aucun résultat d'extraction. Aucun passage N1001–N1500
n'entre dans cette analyse.

Les motifs sont formulés à partir des trois livres de découverte
(*David Copperfield*, *Pride and Prejudice*, *Frankenstein*, 750 passages)
et vérifiés séparément dans *Treasure Island* (250 passages). C'est une
vérification entre livres, pas une mesure de généralisation d'un nouveau
parseur sur des sources inédites. Les quatre livres ont déjà servi au moteur.

## Inventaire des traces

Une occurrence est une proposition observable dans l'arbre sélectionné ou,
pour les citations, dans la préanalyse source. Plusieurs occurrences peuvent
appartenir au même passage. Ces nombres ne sont ni des annotations de vérité
ni un décompte exhaustif des constructions de l'anglais.

| Opération candidate | Variante observée | Découverte | Treasure Island | Total |
| --- | --- | ---: | ---: | ---: |
| `headed_relative_slot_binding` | Objet direct | 33 | 24 | 57 |
| | Sujet | 25 | 7 | 32 |
| | Complément prépositionnel | 17 | 4 | 21 |
| `shared_finite_subject_binding` | Deux VP finis canoniques sous le même NP | 28 | 12 | 40 |
| | Interface structurelle spécialisée | 4 | 0 | 4 |
| `split_speech_attribution` | Un rapporteur entre deux fragments cités | 29 | 20 | 49 |
| `embedded_subject_selection` | Route de contrôle par l'objet avec *to* | 9 | 1 | 10 |
| | Route de causatif sans *to* | 4 | 1 | 5 |

## 1. Relier un même sujet à plusieurs prédicats finis

**`shared_finite_subject_binding`.** Un sujet exprimé alimente les positions
de sujet des deux branches dont la coordination et la portée sont prouvées.
Chaque prédicat garde sa propre voix, sa propre valence et ses propres
compléments. On partage le référent du **groupe nominal**, pas simplement
le premier mot qui lui sert d'ancre.

Dans les 40 paires canoniques (39 passages), une arête exacte du premier
prédicat vers l'ancre sujet apparaît 39 fois, et celle du deuxième **zéro
fois**. Seulement 24 ont une arête `CONJUNCT` entre ces deux ancres.
Les paires proviennent de deux règles, 25 de `vp_coord_finite` et 15 de
`vp_finite_comma_coord_shared_subject`. Q3-56 (*He changed legs again, and
wetted his lips*) et Q3-129 (*Elizabeth looked archly, and turned away*)
rendent le défaut visible sans changer de verbe principal ou de segmentage.

Relecture ciblée des **12 paires canoniques dans Treasure Island**. Elle
porte sur la portée locale et les branches, pas sur la qualité de toute la
phrase.

| Verdict local | Cas et contraste |
| --- | --- |
| Partage effectivement justifié (6) | Q3-469, 485, 831, 833, 846, 847 |
| Contrôle enchâssé pris pour un partage matriciel (1) | Q3-407, dans *He bade me go and leave…*, c'est *me* qui contrôle *go* et *leave* |
| Mauvais niveau de coordination (2) | Q3-431, *suddenly and greatly* coordonne des adverbes. Q3-449, *skulk* s'insère dans l'infinitif, pas dans une série avec *is* |
| Portée ou ancre de sujet erronée (3) | Q3-454, *have* est dans *we should have…*, distinct de *I … looked*. Q3-460, *land* dépend du sujet compris de *paddle*, pas de *it*. Q3-472, le sujet de *was … known* et *carried* est *the name of Captain Flint*, pas le *it* de l'incise |

Deux cas justifiés imposent déjà des contraintes de conception. Q3-469 a
pour sujet *Gray and Ben Gunn*, pas seulement *Gray*. Q3-831 (*The ship is
bought and fitted*) est un passif. Propager le `AGENT` déjà émis pour
*bought* reproduirait un rôle erroné, même avec les deux bons prédicats.
Q3-70 montre aussi qu'une interface spécialisée peut exporter *was* comme
prédicat alors que l'ancre lexicale utile est *getting*. La frontière entre
syntaxe et graphe fait partie de l'opération, pas seulement le nombre
d'arêtes à produire.

## 2. Lier un rôle ouvert de relative à un antécédent

**`headed_relative_slot_binding`.** Propager le propriétaire du rôle
ouvert, son type syntaxique et la preuve locale qui le rend licite.
Le groupe nominal qui accueille la relative fournit l'antécédent. Le
classement reste responsable du choix de ce groupe, et le graphe garde
la distinction entre objet syntaxique et rôle sémantique.

Q3-71 (*a dull life that we lead here*), Q3-355 (*the anguish I suffered*)
et Q3-447 (*a solemn way he had*) répètent l'opération pour l'objet avec des
marqueurs et verbes différents. Q3-213 (*Those that best pleased her*) et
Q3-424 (*the other man who replied*) répètent la liaison du sujet. Sur les
110 traces des routes examinées (91 passages), l'audit ne trouve aucune
arête directe entre les deux **ancres exactes**. Dans 19 des 32 routes sujet,
l'arête part du bon prédicat mais aboutit au marqueur relatif. Ce test ne
prétend pas exclure d'autres conventions de graphe, notamment pour les PP.

**Les 21 traces de lacune PP ont été relues.** Aucune n'a fourni le couple
exact « préposition réellement sans complément + bon antécédent nominal ».
Cela ne veut pas dire que ces relatives n'existent pas dans le corpus.
Q3-66 en contient une (*only one that I know of*) mais le parseur donne
*and* comme antécédent. Dans Q3-232, *woman* est l'objet de *regard* et
*with* garde son complément *too much deference*. Dans Q3-897, *what we
were talking of* ne se rattache pas au nom *Sir*. Les autres traces sont
Q3-41, 63, 110 (deux), 166, 191, 200, 203, 217, 233, 282, 294, 432, 449,
850, 863, 924 et 940. Cette route est un bon **contraste négatif** pour
le mécanisme et une mauvaise base pour activer sa projection.

Q3-839 (*the scheme he had now sketched*) contient, dans la même phrase,
une trace nominale autour de *sketched* et une autre autour de *had*.
Choisir le verbe lexical au lieu de l'auxiliaire est nécessaire, mais
ne suffit pas si le sujet et les limites du sous-arbre sont mal analysés.

## 3. Attribuer un tour cité malgré l'incise du rapporteur

**`split_speech_attribution`.** Conserver un rapporteur pour le tour et
les deux spans source exacts. Ne pas imposer la même structure interne au
contenu produit. La préanalyse repère les trois parties avec des
gouverneurs explicites dans 49 passages sur quatre livres. 27 graphes
contiennent les deux liens observés `REPORTED_CONTENT` (rapporteur vers
premier fragment) et `CONTINUED_SPEECH` (premier vers second).

- Q3-188 et Q3-422 montrent deux contenus enchaînés attribués au rapporteur.
- Q3-44 (*Martha wants … to go to London*) est une seule prédication
  interrompue. Le lien pertinent entre les morceaux est
  `CONTROLLED_COMPLEMENT`. L'absence de `CONTINUED_SPEECH` n'est pas un échec.
- Q3-636 (*Tom … say you forgive me*) attribue l'impératif qui suit au
  rapporteur. Le premier morceau est un vocatif, pas une seconde proposition.
- Q3-442 (*Pew … they've been before us. Someone's turned…*) montre le
  cas inverse. Les trois parties sont dans la source, mais aucune arête
  d'attribution ou de continuité ne les relie dans le graphe sélectionné.

Un nouveau composeur de tours ne doit donc pas chercher « deux
`REPORTED_CONTENT` ». Il peut réutiliser le lien source **rapporteur → tour**,
puis laisser le contenu distinguer une reprise, une prédication interrompue et
une adresse. Deux rapports indépendants ne doivent pas être fusionnés.

## Candidat non prêt — contrôleur du sujet enchâssé

**`embedded_subject_selection`** reste une hypothèse distincte. Dans
Q3-867 (*she pressed me to stay*) ou Q3-286 (*made them enter*), le
complément du verbe principal fournit le sujet compris du verbe enchâssé.
Le lien direct vers ce sujet manque dans les 15 traces inspectées par
l'observateur. Mais cinq analyses avec *have* ne justifient pas l'objet
comme contrôleur. Dans Q3-168 (*she had a less active part to play*),
*she* joue le rôle, et *part* est ce qu'elle joue. Unifier les règles
simplement parce qu'elles ont la forme `V NP to VP` entérinerait le défaut.
Il faut des preuves distinctes pour le contrôle sujet, le contrôle objet,
les causatifs et le complément d'un nom.

## Ordre d'essai

1. Commencer par la liaison du sujet commun aux **VP finis actifs** avec
   sujet simple et deux prédicats lexicaux prouvés sur Novel-1000. Mesurer
   séparément le bon candidat au rang 1 et les relations du graphe. Les
   vrais cas de passif et de sujet coordonné restent des contrastes, comme
   les faux partages Q3-407 et Q3-454. Aucune copie automatique de label.
2. Pour les relatives, commencer par rendre le rôle explicite en lecture
   seule. Tester objet et sujet avec des antécédents confirmés, et garder
   les faux PP comme négatifs. Ne pas écrire une arête d'objet sur la
   seule foi de `gap=object`.
3. Pour la parole, réutiliser d'abord le lien source du rapporteur au tour.
   Valider séparément les conséquences pour le contenu et les destinataires.

Un patron existant ne disparaît qu'après vérification des autres
attachements qu'il protégeait. Aucun changement de parseur, de grammaire,
de corpus, de file de cas ou de budget dans cet audit.

## Reproduction

```sh
export PYTHONPATH=superparser
python -m scripts.novel_source_reporting_v3 replay --group all \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel1000-v3
python -m scripts.novel_source_reporting_v3 check --out-dir /tmp/novel1000-v3
python -m scripts.audit_novel1000_patterns --replay-dir /tmp/novel1000-v3
python -m unittest -q superparser.tests.test_audit_novel1000_patterns
```

Le dernier audit de données inclut les IDs, règles, ancres, spans et arêtes
observables par passage. Ajouter `--summary-only` pour les seuls effectifs.
Voir [l'audit de réemploi initial](SCOPED_GRAMMAR_REUSE_AUDIT.md) pour les
statistiques de portées et l'origine du contrat des relatives.
