# Les 50 phrases à reprendre — Novel-500

Inventaire de départ après la [PR #58](https://github.com/leye0/seman2/pull/58), à 450/500 analyses complètes et 30/30 dialogues historiques. Textes et statuts issus du [rapport Novel-500](https://github.com/leye0/seman2/actions/runs/43432601124).

**Suivi après la [PR #68](https://github.com/leye0/seman2/pull/68)** — 475/500, 25 phrases restantes. Les trois temporelles finies #73, #95 et #348 sont résolues. Prochain lot à examiner : #206 et #246, des temporelles qui doivent rester à l’intérieur d’un supplément nominal. La parenthèse explicite de #360 demeure dans la file structurelle.

**Suivi après la [PR #67](https://github.com/leye0/seman2/pull/67)** — 472/500, 28 phrases restantes. Le lot #242 et #469 sur les relatives détachées attachées à un groupe nominal interne est résolu. Prochain lot à examiner : #73, #95 et #348, des temporelles finies placées à différents niveaux. La parenthèse explicite de #360 demeure dans la file structurelle.

**Suivi après la [PR #66](https://github.com/leye0/seman2/pull/66)** — 470/500, 30 phrases restantes. Le lot #363 et #480 sur les relatives imbriquées et les suppléments est résolu. Prochain lot à examiner, #242 et #469, relatives supplémentaires attachées à un groupe nominal interne. La parenthèse explicite de #360 demeure dans la file structurelle.

**Suivi après la [PR #65](https://github.com/leye0/seman2/pull/65)** — 468/500, 32 phrases restantes. Le lot #328 et #499 sur les relatives à complément manquant imbriqué est résolu. Prochains cas à examiner ensemble : #363 et #480, relatives avec un complément manquant sous un autre prédicat.

**Suivi après la [PR #64](https://github.com/leye0/seman2/pull/64)** — 466/500, 34 phrases restantes. Le lot #228 et #337 sur les infinitifs sélectionnés par un adjectif est résolu. Prochain lot à explorer : #328 et #499 sur les relatives à complément manquant imbriqué.

**Suivi après la [PR #63](https://github.com/leye0/seman2/pull/63)** — 464/500, 36 phrases restantes. Le lot #226 et #350 sur le groupe de manière interposé est résolu. Prochain lot à explorer : #228 et #337 sur les adjectifs qui sélectionnent un infinitif.

**Suivi après la [PR #62](https://github.com/leye0/seman2/pull/62)** — 462/500, 38 phrases restantes. Le cas #113 avec point-virgule et coordinations imbriquées est résolu. Le prochain témoin à sujet partagé est #226.

**Suivi après la [PR #61](https://github.com/leye0/seman2/pull/61)** — 461/500, 39 phrases restantes. Premier lot à sujet partagé (#69, #189 et #372) résolu. Prochain témoin de cette famille : #113 et ses coordinations imbriquées.

**Suivi après la [PR #60](https://github.com/leye0/seman2/pull/60)** — 458/500, 42 phrases restantes. Le lot « sujet interrompu puis prédicat repris » est résolu. Les statuts historiques ci-dessous restent ceux du relevé de départ.

Les textes sont intégraux. Le classement distingue des structures observées à examiner, pas des causes déjà établies. Un délai ou une saturation ne prouve pas que la grammaire manque.

Priorité aux parenthèses explicites, puis aux incises et suppléments. Vérifier le paragraphe source et les frontières avant de modifier la grammaire, puis inspecter le premier arbre et comparer les 500 mêmes phrases.

Statuts de départ : 5 délai, 5 forêt saturée, 7 aucune racine, 33 racines sans analyse valide.

## P1 — Parenthèses explicites (2)

| Cas | Statut de départ | Texte source intégral | Structure à vérifier |
| --- | --- | --- | --- |
| #493 | Aucune racine | I should lie down in my own place (I thought with a silent chuckle) and enjoy their faces when they found me in the morning. | Incise de pensée entre deux prédicats sous un seul modal. Premier cas traité. |
| #360 | Aucune racine | Or (so my fond fancy imaged) some accident might meanwhile occur to destroy him and put an end to my slavery forever. | Incise introduite par so, juste après Or. La principale reste à prouver séparément. |

## P2 — Incises, suppléments et ruptures apparentées (16)

| Cas | Statut de départ | Texte source intégral | Structure à vérifier |
| --- | --- | --- | --- |
| #73 | Délai | I thought, as they came towards us, that they were well matched even in that particular. | Temporelle entre thought et le complément en that. — Corrigé par la PR #68. |
| #87 | Racines sans analyse valide | We judged it expedient, now, to tell her all we knew; which I recounted at length. | Incise now dans it…to, puis relative après le point-virgule. |
| #95 | Forêt saturée | Accordingly, when Mr. Peggotty came home about nine o’clock, this unfortunate Mrs. Gummidge was knitting in her corner, in a very wretched and miserable condition. | Temporelle intercalée après Accordingly, puis ajout descriptif final. — Corrigé par la PR #68. |
| #101 | Racines sans analyse valide | My face, neck, and hands, from unaccustomed exposure to the air and sun, were burnt to a berry-brown. | Groupe prépositionnel causal entre le sujet coordonné et le passif. — Corrigé par la PR #60. |
| #189 | Racines sans analyse valide | Miss Bennet had slept ill, and though up, was very feverish, and not well enough to leave her room. | Concessive réduite though up au milieu de prédicats coordonnés. — Corrigé par la PR #61. |
| #220 | Aucune racine | He was at the same time haughty, reserved, and fastidious, and his manners, though well-bred, were not inviting. | Concessive réduite though well-bred entre sujet et prédicat. — Corrigé par la PR #60. |
| #226 | Aucune racine | He inquired how far Netherfield was from Meryton; and, after receiving her answer, asked in a hesitating manner how long Mr. Darcy had been staying there. | Gérondif after receiving her answer intercalé entre deux interrogatives indirectes. — Corrigé par la PR #63. |
| #239 | Forêt saturée | Elizabeth immediately recognizing the livery, guessed what it meant, and imparted no small degree of her surprise to her relations by acquainting them with the honour which she expected. | Participiale entre le sujet et guessed, puis gérondif de moyen. — Corrigé par la PR #60. |
| #246 | Aucune racine | Anxious and uneasy, the period which passed in the drawing-room, before the gentlemen came, was wearisome and dull to a degree that almost made her uncivil. | Supplément adjectival détaché, puis temporelle intercalée dans le sujet. |
| #319 | Racines sans analyse valide | Now my desires were complied with, and it would, indeed, have been folly to repent. | Incise indeed entre modal et infinitif parfait. |
| #463 | Racines sans analyse valide | He himself, I thought, looked somewhat paler and more stern than I was used to. | Incise de pensée entre le sujet emphatique et le prédicat comparatif. — Corrigé par la PR #60. |
| #480 | Racines sans analyse valide | The squire was sitting down, as white as a sheet, thinking of the harm he had led us to, the good soul! | Équative détachée, participiale et reprise nominale finale. — Corrigé par la PR #66. |
| #485 | Racines sans analyse valide | I snatched a cutlass from the pile, and someone, at the same time snatching another, gave me a cut across the knuckles which I hardly felt. | Participiale incidente entre sujet et gave. — Corrigé par la PR #60. |
| #486 | Aucune racine | These biscuits, should anything befall me, would keep me, at least, from starving till far on in the next day. | Conditionnelle inversée sans if entre sujet et modal, puis at least. — Corrigé par la PR #60. |
| #496 | Racines sans analyse valide | The air, besides, was fresh and stirring, and this, under the sheer sunbeams, was a wonderful refreshment to our senses. | Incises distinctes dans deux propositions coordonnées. |
| #499 | Forêt saturée | Two of the bars, slung in a rope's end, made a good load for a grown man--one that he was glad to walk slowly with. | Participiale passive dans le sujet, puis reprise en one après un tiret non apparié. — Corrigé par la PR #65. |

## P3 — Relatives, appositions et comparatifs (11)

| Cas | Statut de départ | Texte source intégral | Structure à vérifier |
| --- | --- | --- | --- |
| #80 | Racines sans analyse valide | It was difficult to believe that a night so long to me, could be short to anybody else. | Comparatif et virgule historique avant le prédicat enchâssé. |
| #84 | Racines sans analyse valide | Never, never, had I loved Dora so deeply and truly, as I loved her that night. | Inversion après Never répété, puis comparaison en as. |
| #110 | Délai | She knew no more than I did, where he was going, but she thought he had some project shaped out in his mind. | Comparatif elliptique no more than I did avant le contenu interrogatif where. |
| #166 | Racines sans analyse valide | Charlotte the wife of Mr. Collins was a most humiliating picture! | Apposition nominale sans virgule après le nom propre. |
| #206 | Délai | Mrs. Reynolds then directed their attention to one of Miss Darcy, drawn when she was only eight years old. | Ellipse nominale dans one of Miss Darcy et supplément participial drawn when… |
| #242 | Racines sans analyse valide | She had never heard of his having had any relations, except a father and mother, both of whom had been dead many years. | Gérondif possessif parfait, exception et relative partitive. — Corrigé par la PR #67. |
| #291 | Racines sans analyse valide | A meeting, which he anticipated with such joy, so strangely turned to bitterness. | Relative supplémentaire au milieu du sujet. — Corrigé par la PR #60. |
| #294 | Racines sans analyse valide | Who could arrest a creature capable of scaling the overhanging sides of Mont Saleve? | Interrogative à sujet who et adjectif capable suivi d’un gérondif. |
| #328 | Racines sans analyse valide | These sublime and magnificent scenes afforded me the greatest consolation that I was capable of receiving. | Relative à objet direct non exprimé de receiving. — Corrigé par la PR #65. |
| #363 | Racines sans analyse valide | Sometimes I sat with my eyes fixed on the ground, fearing to raise them lest they should encounter the object which I so much dreaded to behold. | Supplément participial, subordonnée en lest et relative à complément infinitival. — Corrigé par la PR #66. |
| #469 | Aucune racine | I remember the appearance of his coat, which he patched himself upstairs in his room, and which, before the end, was nothing but patches. | Relatives coordonnées sur le même antécédent, avec incise dans la seconde. — Corrigé par la PR #67. |

## P4 — Frontières entre propositions, coordinations et ellipses (17)

| Cas | Statut de départ | Texte source intégral | Structure à vérifier |
| --- | --- | --- | --- |
| #69 | Délai | I informed her that he sent his compliments, and was getting on very well indeed. | Complément en that avec deux prédicats partageant he. — Corrigé par la PR #61. |
| #113 | Racines sans analyse valide | Here she ceased; and snapping her reticule again, and shutting her mouth, looked as if she might be broken, but could never be bent. | Point-virgule, sujet implicite et participiales coordonnées. — Corrigé par la PR #62. |
| #122 | Racines sans analyse valide | Mr. Micawber considered it necessary to prepare either my aunt or his wife, by degrees, and said, sooner than he had expected yesterday. | Coordination de considered et said, contenu implicite de said, comparatif temporel détaché. |
| #124 | Racines sans analyse valide | If that were so, my sacrifice was nothing; my plainest obligation to her unfulfilled; and every poor action I had shrunk from, I was hourly doing. | Parallélisme au point-virgule, copule élidée et objet antéposé. |
| #221 | Forêt saturée | Mrs. Bennet was prevented replying by the entrance of the footman with a note for Miss Bennet; it came from Netherfield, and the servant waited for an answer. | Passif avec gérondif, puis propositions distinctes au point-virgule. |
| #228 | Racines sans analyse valide | Mrs. Hurst and her sister scarcely opened their mouths, except to complain of fatigue, and were evidently impatient to have the house to themselves. | Except to à portée verbale et coordination de prédicats. — Corrigé par la PR #64. |
| #238 | Racines sans analyse valide | That he should even speak to her was amazing!--but to speak with such civility, to inquire after her family! | Sujet propositionnel en that, puis infinitifs détachés à valeur exclamative. |
| #249 | Racines sans analyse valide | Its effect was most extraordinary; for on first hearing it, Mrs. Bennet sat quite still, and unable to utter a syllable. | Point-virgule causal en for et coordination adjectivale sous sat. |
| #337 | Racines sans analyse valide | I was unable to pursue the train of thought; a thousand feelings pressed upon me, and I wept bitterly. | Point-virgule suivi d’une coordination entre propositions indépendantes. — Corrigé par la PR #64. |
| #348 | Racines sans analyse valide | When I mingled with other families I distinctly discerned how peculiarly fortunate my lot was, and gratitude assisted the development of filial love. | Temporelle initiale sans virgule, interrogation indirecte et coordination finale. — Corrigé par la PR #68. |
| #350 | Forêt saturée | He heard with attention the little narration concerning my studies and smiled at the names of Cornelius Agrippa and Paracelsus, but without the contempt that M. Krempe had exhibited. | Prédicats coordonnés, contraste en but without et relative. — Corrigé par la PR #63. |
| #362 | Racines sans analyse valide | I enjoyed this scene, and yet my enjoyment was embittered both by the memory of the past and the anticipation of the future. | Coordination de propositions, puis both…and sous la même préposition. |
| #371 | Délai | It rang on my ears long and heavily; the mountains re-echoed it, and I felt as if all hell surrounded me with mockery and laughter. | Point-virgule, coordination et comparaison hypothétique as if. |
| #372 | Racines sans analyse valide | The Greeks wept for joy when they beheld the Mediterranean from the hills of Asia, and hailed with rapture the boundary of their toils. | Prédicats coordonnés, avec une subordonnée temporelle dans le premier. — Corrigé par la PR #61. |
| #373 | Racines sans analyse valide | I wish to soothe him, yet can I counsel one so infinitely miserable, so destitute of every hope of consolation, to live? | Coordination adversative avec inversion interrogative et suppléments adjectivaux. |
| #462 | Racines sans analyse valide | At least, and at last, I was off the sea, nor had I returned thence empty-handed. | Adverbiaux initiaux coordonnés, puis inversion en nor. |
| #477 | Racines sans analyse valide | The HISPANIOLA was laid a couple of points nearer the wind and now sailed a course that would just clear the island on the east. | Prédicats coordonnés à sujet partagé, comparatif nautique et relative. |

## P5 — Subordination et sélection des compléments (4)

| Cas | Statut de départ | Texte source intégral | Structure à vérifier |
| --- | --- | --- | --- |
| #74 | Racines sans analyse valide | However much astonished I might be, I was sensible that I had no right to refuse compliance with such a peremptory command. | Concessive de degré et adjectif sensible suivi d’un complément en that. |
| #111 | Racines sans analyse valide | That condition was, that he should make a solemn resolution to grant no more loans of his name, or anything else, to Mr. Micawber. | Complément prédicatif en that et alternative nominale détachée. |
| #213 | Racines sans analyse valide | But, perhaps he could not in her mother's presence be what he was before her uncle and aunt. | Groupe prépositionnel entre le modal nié et be, puis propositions en what et before. |
| #358 | Racines sans analyse valide | The sight of the awful and majestic in nature had indeed always the effect of solemnizing my mind and causing me to forget the passing cares of life. | Gérondifs coordonnés sous of, puis infinitif sélectionné par causing. |
