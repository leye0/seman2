# Point de reprise — AGENT ChatGPT, commencer ici

**Dépôt privé : `leye0/seman2`, branche de travail `main`.**
**SOURCE TECHNIQUE ABSOLUE : [`RUN_CURRENT_LAYER1.md`](RUN_CURRENT_LAYER1.md).**
**PROTOCOLE OBLIGATOIRE DE CORRECTION D'UNE PHRASE : [`GRAMMAR_CASE_FIX_PROTOCOL.md`](GRAMMAR_CASE_FIX_PROTOCOL.md).**
Ce document est un aide-mémoire humain; si un ancien compte rendu contredit le code actuel ou RUN_CURRENT_LAYER1, vérifier `main` et suivre ce dernier.

## ÉTAT COURANT — PR #43, 30 vrais dialogues en référence (12 novembre 2026)

- **PR #43 fusionnée** à `main` : [diff et discussion](https://github.com/leye0/seman2/pull/43), commit `8e0acda7d9748a4ea916497ae58eb8c0977998f9`. Tous les **30 passages de discours direct initialement en échec** sont désormais gelés par `case_id` et empreinte de cohorte dans `scripts.audit_anchored_dialogue_30`. Même cohorte, mêmes budgets et même passerelle grammaticale, sans exclusion sélective ni remplacement du corpus.
- **Diagnostic officiel : [run #43154183121](https://github.com/leye0/seman2/actions/runs/43154183121)** : **414/500 complets, 86 résidus**, SHA `d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`. Par rapport au 411/500 précédent sur les **mêmes 500 textes**, les passages **#11, #137, #413** sont maintenant complets, **0 réussite précédente perdue**. Les 30 dialogues de départ passent de **0/30 à 3/30 complets**, soit **27 encore en échec**.
- **Constructions ajoutées depuis le point de départ des 30 :** #413, réponse adverbiale + vocatif + incise; #11, titre nominal avec citation imbriquée, dont les sous-arbres `DET` et `NP` sont prouvés indépendamment; #137, réponse modale avec topicalisation et ellipse verbale explicitement **non résolue**, jamais reconstituée artificiellement.
- **[Core CI #43154183122](https://github.com/leye0/seman2/actions/runs/43154183122)** verte : **667 tests**, **120/120 gold**, **24/24 contrastes grammaticaux**. L'audit actif répartit les **27 dialogues encore en échec** en 6 citations multiphrases, 1 citation imbriquée, 7 citations avec incise et discours interrompu, 7 citations simples avec attribution et 6 citations sans attribution.
- **Analyse des obstacles :** la couche propose un plan de composition pour certaines citations encore échouées, mais **une proposition n'est pas un arbre prouvé**. Le rapport `anchored_dialogue_30.json` conserve source exacte, constituants, relations, plans et statut réel par cas. **12/30 cas n'ont même pas de plan de composition actuellement**. Il reste en particulier les subordonnées séparées par incise, les questions/dialectes, les citations multiphrases complexes et les anaphores interparagraphes.
- **File officielle mise à jour** : `docs/GRAMMAR_CASE_QUEUE.json`, 86 résidus, prochain index **22** (`766:3f699ef32c5f0e6a`). Le score 414 est une réussite du parseur, **pas une certification automatique de tous les rattachements sémantiques rang 1**. Prochaine progression : traiter les constructions les plus représentées parmi ces 27 cas avec tests adversariaux d'attachement et comparer exactement les mêmes 500 phrases.

## HISTORIQUE — PR #42, composition initiale des dialogues (11 novembre 2026)

- **PR #42 fusionnée** au commit `3e225f6e7cada310df7debec12164beb839b3bb0` (branche testée `25f3b483f192affcfca46da8abecbe45add43a60`). **La couche structurelle est maintenant effectivement transmise à `Parser.parse`** via le seul `parse_corpus_case`; son graphe n'est plus seulement un audit.
- **Code intégré :** `seman_parser.quoted_discourse` identifie propositions prononcées, incises, reprises de parole, citations imbriquées et narrations intercalées avec les offsets exacts. `seman_parser.structural_composition.QuotedSentenceComposer` découpe uniquement des cas justifiés par le texte, vérifie **chacun des sous-arbres** avec le reconnaisseur grammatical existant, puis assemble leurs `SegmentInterface` avec les règles déclaratives `data/dialogue_structural_grammar.jsonl`. Aucun guillemet, ponctuation ou verbe n'est inventé. Les dépendances forment un graphe acyclique contrôlé par la passerelle.
- **Constructions grammaticalement licenciées :** citation de 2 ou 3 propositions finies indépendantes; deux propositions finies séparées par une **incise `SPEECH-TAG` grammaticalement vérifiée**; réponse adverbiale avec vocatif (énoncé mineur sans verbe), par exemple `‘Perfectly, sir.’`. Les relations sémantiques des arbres complets incluent `REPORTED_CONTENT`, `CONTINUED_SPEECH`, `AGENT`. **Pas encore de composition générale des subordonnées interrompues, des ellipses anaphoriques ou des dialogues interparagraphes.**
- **Validation #43102702013** : 657 tests réussis, **120/120** annotations de référence, **24/24** contrastes positifs; test explicite des liens sémantiques et des sous-arbres grammaticaux. [Voir les tests](https://github.com/leye0/seman2/actions/runs/43102702013).
- **Même cohorte 500, exactement les mêmes textes source**, SHA `d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f` : **410 → 411 analyses complètes**; le cas **#19 `‘Perfectly, sir.’`** passe `no_structural_root → complete`, preuves `ADV + COMMA + NP` et guillemets originaux. **410 réussites antérieures préservées, 0 régression**. Deux autres cas (#110, #206) demeurent incomplets mais passent de `timeout` à `kbest_budget_exceeded`. Aucun autre cas n'est réparé. [Diagnostic #43102702010](https://github.com/leye0/seman2/actions/runs/43102702010).
- **Nouvelle file officielle :** `docs/GRAMMAR_CASE_QUEUE.json`, **89 échecs** (57 racines invalides, 16 sans racine, 11 saturations de forêt, 2 plafonds k-best, 3 timeouts), prochain **#11** (`766:7aeedec565c8d7f5`). Audit des citations source : 157 cas, 30 échecs, contre 59 échecs parmi les 343 unités sans citation.
- **Limites et prochaine étape :** traiter les **subordonnées et groupes discursifs interrompus par une incise** par leurs interfaces syntaxiques exactes, ensuite les citations interparagraphes. Ne pas augmenter le score en réétiquetant un fragment, ni élargir l'assemblage à des structures non grammaticalement prouvées.

## HISTORIQUE — classification des fonctions discursives (PR #41, état précédent)

- **PR #41 fusionnée** au commit `106347aa814b3cc86a740a33e6f57bc586991f25`; version validée `bf0f2d53373430f35f09b7a7ee34f0209228fe36`. `seman_parser.discourse_roles` distingue désormais **ellipse rétrospective liée au texte antérieur**, **continuation de discours rapporté**, **notation documentaire de navigation**, **post-scriptum documentaire**, **réponse elliptique légitime** et **formule de salutation / clôture**. La première phrase de la grammaire n'est plus obligatoirement classée `matrix_clause` pour ces unités.
- Exemples réels : `Only upon us two.` est une reprise dépendante de `He pushed ... closed the door upon us.`; `‘--was induced...` exige la construction précédente; les relèvements cartographiques `bearing a point to the N. of N.N.E.` et les post-scriptums sortent du benchmark narratif, mais conservent des **constituants internes typés** et leurs offsets. `‘Perfectly, sir.’` et `Good night, my sister.` sont des **énoncés mineurs légitimes**, conservés.
- Les références de gouverneur inter-énoncé sont uniquement des **candidats fondés sur les positions réelles** du livre, pas des références sémantiques prouvées. Aucune ponctuation ni aucun mot n'est ajouté. Les heuristiques de navigation ne codent plus les noms des lieux du roman.
- **[CI Core #43091320052](https://github.com/leye0/seman2/actions/runs/43091320052) verte : 635 tests, 120/120 gold, 24/24 contrastes.** **[Diagnostic 500 #43091319834](https://github.com/leye0/seman2/actions/runs/43091319834) vert : SHA `d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`, 410/500, 90 résidus** (57 racines invalides, 17 sans racine, 11 forêts saturées, 5 délais; 0 erreur). Nouvelle cohorte, aucune soustraction naïve à 411/500.
- Comparaison exacte sur les textes identiques des anciennes/nouvelles cohortes : **435 communs, 434 statuts inchangés et 1 délai devenu complet, 0 régression observée**. Les 65 remplacements sont dus à l'échantillonnage, pas à de nouvelles règles grammaticales.
- Audit sur quatre romans : **22 125 unités**, **69 385 constituants source**, **382 énoncés mineurs**, **16 unités contextuelles** (15 continuations de discours + 1 ellipse), **3 unités documentaires**, **0 ponctuation synthétique**. Les 906 autres problèmes de citation/contexte ne sont pas magiquement résolus.
- **File courante** : `docs/GRAMMAR_CASE_QUEUE.json` (90 résidus), prochaine position **11**, `case_id=766:7aeedec565c8d7f5`.
- Limites : `Parser.parse` ne consomme pas encore les références de discours et les constituants provisoires pour composer/pruner ses analyses; les enchaînements complexes interparagraphes et les énoncés mineurs restent des sujets de recherche. Ne pas faire passer une réduction de faux exemples pour un progrès de couverture grammaticale.

## HISTORIQUE — préanalyse des énoncés complets (PR #40, état précédent)

- **PR #40 fusionnée** au commit `68fbb3d1c46e5b739c7d94cfb924dc6b85c82ec0`, arbre de code identique à la branche testée `ae494bc7df12a983554974de4975b0250e158681`. Le chemin de production est maintenant `gutenberg_novels.analysis_units → structural_preanalysis.analyze_paragraph → extract → parse_corpus_case → Parser.parse`.
- **Changement de niveau architectural :** les frontières des unités respectent les citations multipartites; les points-virgules ne découpent plus les phrases du corpus. Les constituants ont `function`, `relation`, `governor`, `evidence` et offsets sources originaux. Citations non closes dans le paragraphe = `requires_source_context`, pas de ponctuation inventée, pas de réussite prétendue.
- **Couche structurelle provisoire, PAS analyse finale :** les attributs et références sont audités et exposés à `PreparedCorpusInput`, mais `Parser.parse` ne consomme pas encore le graphe pour construire ou limiter sa forêt syntaxique. Les phrases longues et les discours d'un paragraphe à l'autre restent une priorité.
- **CI Layer 1 [#43080700620](https://github.com/leye0/seman2/actions/runs/43080700620) verte : 627 tests, 120/120 gold, 24/24 contrastes positifs.** Les 29 témoins grammaticaux historiques sont figés en fixtures source, sans imposer leurs vieux indices au découpeur courant.
- **CI romans [#43080700568](https://github.com/leye0/seman2/actions/runs/43080700568) verte : cohorte SHA `140097d47116afac4172bd87b32bff8f9628e53a270c6b1dcca85d74a4b0cfe4`, **411/500**, **89 résidus** (18 sans racine, 54 racines sans analyse valide, 11 limites de forêt, 6 délais, 0 erreur). Échantillon différent : 411 n'est PAS une régression mesurée contre 416 ou 425.
- **Audit complet :** 11 144 paragraphes et 22 125 unités de discours, dont 21 219 admissibles et 906 nécessitant du contexte; 69 379 constituants typés, 10 875 citations appariées; **0 ponctuation synthétique et 0 découpage de point-virgule**.
- **Sur les 500 anciennes positions sources [#43080700618](https://github.com/leye0/seman2/actions/runs/43080700618) :** 326 changent d'étendue, 174 inchangées, 451 provisoirement complètes, 49 encore contextualisées, 487 unités distinctes. Ce n'est PAS une évaluation de succès grammatical sur le même jeu.
- **Nouvelle file active** : `docs/GRAMMAR_CASE_QUEUE.json`, 89 résidus, prochain index `16`, `case_id=766:15fcebb30fe8216f`. Références précédentes dans les sections ci-dessous = historiques.
- **Prochaine étape de recherche :** transformer les rapports de discours `requires_source_context` en véritables unités complètes interparagraphes, puis utiliser les dépendances source de haut niveau pour produire une analyse compositionnelle correcte, sans multiplication de règles de grammaire destinées à réparer des fragments.

## Historique — première couche de cohésion (PR #38, remplacée dans le chemin de production)

- La [PR #38](https://github.com/leye0/seman2/pull/38) est **fusionnée** au commit `14aba462789392e6b9b38434fc8b187b520cd3f2`. Le module `superparser/seman_parser/structural_units.py` intervient explicitement après la segmentation ponctuationnelle et avant les unités passées au parseur, et documente chaque lien par sa justification structurale. Il ne fait aucun parsing complet et n'emploie aucun lexique alternatif. Les guillemets et spans source restent dans le pipeline existant.
- [CI Layer 1 #43046480644](https://github.com/leye0/seman2/actions/runs/43046480644) **verte** : **619 tests**, 120/120 annotations, 24/24 contrastes positifs, 9 négatifs toujours acceptés, smoke canonique/adaptatif/dialogue OK. Les anciens tests #434 et #438, dont l'index provenait du vieux corpus, ont été convertis en témoins par texte source.
- [CI nouvelle cohorte #43046480613](https://github.com/leye0/seman2/actions/runs/43046480613) **verte** : nouveau SHA `5e2756f664fb05805cb70b48edb2815fb32544dd1187470a9759e1174af51c7b`, **416/500**, **84 résidus** : 18 `no_structural_root`, 54 `roots_without_valid_analysis`, 9 limites de forêt, 3 délais; 0 erreur. **Aucune comparaison directe de 416 avec 425 ou 475** : le rééchantillonnage a changé.
- Comparaison par `case_id` avec la cohorte précédente : **137 unités communes, 0 changement de statut**. Les 75 anciens résidus comprenaient 27 unités issues de points-virgules; cela ne prouve pas que les 27 étaient des erreurs de découpage.
- Audit prégrammatical sur quatre romans : **37 081 unités** (37 410 précédemment), mêmes 11 144 paragraphes, 19 raccordements avec normalisation d'espaces, aucune perte de caractère non blanc. Le rapport CI inventorie les **motifs de regroupement**; ces regroupements ne constituent pas des preuves d'arbres corrects.
- Audit historique de la grammaire `scripts.audit_fragment_grammar_rules` : **374 règles le 11 octobre** contre **608** aujourd'hui, **266 nouveaux IDs, 32 retirés**; **45 règles candidates à l'examen** (29 introduites depuis le 11 octobre, 16 plus anciennes). **Aucune règle supprimée par simple heuristique**; le rapport source/JSON est dans l'artefact de la CI. Toute suppression devra vérifier les arbres de rang 1 et les positifs/négatifs indépendants.
- La file courante `GRAMMAR_CASE_QUEUE.json` a été **reconstruite à partir de ce nouveau run** : 84 résidus, curseur `-1`, **prochain index 1**, `case_id=766:e0afb5059ab6d771`.

## Recherche active — couche de cohésion structurale et audit des règles

La branche [`feat/structural-cohesion-layer`](https://github.com/leye0/seman2/tree/feat/structural-cohesion-layer)
introduit un module structural **distinct** entre la segmentation
ponctuationnelle et l'extraction grammaticale : chaque point-virgule reçoit
une justification de jonction ou de séparation. Les tests adverses assurent
que les propositions autonomes ne sont pas fusionnées arbitrairement.
Un audit séparé inventorie les productions grammaticales qui pourraient
avoir compensé des coupures artificielles; aucune n'est supprimée sans
ablation et vérification de l'arbre sélectionné. Après changement des
frontières, la cohorte SHA et sa file de cas doivent être régénérées.

## État confirmé après la migration — cohorte actuelle, 11 novembre 2026

- **PR #37 fusionnée** au commit `e2265953a7c78e504bed6deee3b9823ed7267c21` : un seul découpeur source-conservateur et dépendance-aware pour toute extraction littéraire, **plus aucune sélection v1/v2 dans les API actives**. La grammaire reste accessible uniquement par le passage `parse_corpus_case → Parser.parse` pour les cas du corpus. Les anciens algorithmes et indices sont accessibles via l'historique Git, pas par un chemin production alternatif.
- **Nouvelle cohorte de 500** : SHA `851878102fb4305edbbe3530b54b33fdc22af82428773440f4dd35111c6d1d77`, obtenu deux fois en CI. [Action Layer 1 #43029431199](https://github.com/leye0/seman2/actions/runs/43029431199) verte : **610 tests**, 120/120 annotations, 24/24 contrastes positifs, 9 négatifs acceptés comme précédemment, smoke canonique/adaptatif/dialogue OK. [Action 500 #43029431200](https://github.com/leye0/seman2/actions/runs/43029431200) verte : **425/500** reconnus, **75** résidus (20 sans racine, 46 racines invalides, 4 forêts saturées, 5 délais).
- L'ancien **475/500** portait sur une **cohorte différente** et n'est pas comparable au 425/500 comme évolution de la grammaire. Les **242 cas communs**, appariés par identité de source, montrent **zéro changement de statut** (236 reconnus, 5 échecs structurels, 1 délai); aucune régression de statut observée sur cette intersection.
- Audit séparé du découpage : **37 410 unités**, **11 144 paragraphes**, quatre romans nettoyés, caractères non blancs conservés, **19 variations d'espacement** au raccordement des unités; la reconstruction strictement octet-par-octet n'est **pas certifiée**. Les frontières sont vérifiées par quatre constructions dépendantes positives et trois indépendantes négatives.
- File déterministe [`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json) **régénérée à partir du rapport de la nouvelle cohorte** : 75 résidus avec leur `case_id` stable, `last_attempted_index=-1`, **prochain cas = index 1** (et non l'ancien 109). Toute nouvelle modification des frontières impose un nouveau SHA et un nouveau point de départ.
- **Toutes les sections ci-dessous relatant les cas 8, 64, 94, 105, 109, etc. et le 475/500 sont des comptes rendus historiques**, dont les anciens indices ne peuvent être reportés sur la nouvelle cohorte.

## Migration du système : un seul découpeur actif (novembre 2026)

La [PR #37](https://github.com/leye0/seman2/pull/37) supprime la sélection
v1/v2 et bascule **tous les extraits** de romans sur les frontières
dépendantes/citations. La cohorte 500 et la file doivent être reconstruites :
**les indices 8, 64, 94, 105, 109, etc. et le score 475/500 décrits
ci-dessous sont des snapshots de l'ancienne cohorte**. Après migration,
l'état de référence actuel se trouve uniquement dans
[`CURRENT_COHORT.json`](CURRENT_COHORT.json),
[`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json) et la dernière
Action `novel-parse-diagnostics` verte. Ne jamais reprendre un ancien
numéro de cas sans vérifier son identité.

## Mise à jour — cas 105, segmentation d'abord (11 novembre 2026)

- La [PR #36](https://github.com/leye0/seman2/pull/36) est **fusionnée** au commit `153340896b92516ced375c4a295b17cb5cc955fd`. **Cause établie** : la v1 historique coupait à l'intérieur des deux questions d'une citation imbriquée dans *David Copperfield*, isolant `Oh, Martha, can it be you?”--for ...` de `‘Says Em’ly, “Martha, is it you?`.
- **Correction** dans `sentence_boundaries.py` : la segmentation **prospective v2**, lorsqu'une citation ouverte contient une dernière phrase complète puis une fermeture suivie d'une explication causale `--for`/`—for` ou `because`, conserve la construction contiguë. Deux positifs indépendants et des négatifs démontrent le comportement; aucun changement de grammaire, budgets, WordNet, cohorte v1 ou moteur.
- CI [Layer 1 #42962215639](https://github.com/leye0/seman2/actions/runs/42962215639) **verte** : **610 tests**, smoke, 120/120 annotations, 24/24 positifs, 9/24 négatifs acceptés connus. CI [500 #42962215919](https://github.com/leye0/seman2/actions/runs/42962215919) **verte** : **475/500**, 25 résidus; même SHA de cohorte `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- La **file v1** garde le cas 105 parmi les échecs (il n'est pas grammaticalement reconnu dans l'échantillon historique); une annotation distincte indique le découpage v2 réparé. `last_attempted_index=105`; **prochain index déterministe : 109**. On ne revendique ni 476/500 ni un arbre grammatical complet pour la version v2.
- Le [protocole](GRAMMAR_CASE_FIX_PROTOCOL.md) impose désormais **avant toute modification grammaticale** la lecture du paragraphe original, de ses voisins et des frontières v1/v2 afin de détecter systématiquement ces faux résidus.

## Intégration confirmée le 11 novembre 2026 — cas 96

- La PR [#35](https://github.com/leye0/seman2/pull/35) a été **fusionnée** sur `main` au commit `551395dbf874698d5c145bdf24631b388cde279f` après validation de son arbre **de rang 1** et des attaches exactes. Elle ajoute une lecture locative nominalisée de `wherever` sans supprimer les lectures antérieures, et une composition typée `DASH + WH-NOM + CLAUSE` dans le dialogue. Voir [le dossier du cas 96](CASE_96_DASH_LOCATIVE_FREE_RELATIVE.md).
- La CI [Layer 1 #42957398567](https://github.com/leye0/seman2/actions/runs/42957398567) est verte : **608 tests**, smoke canonique/adaptatif/dialogue, **120/120** annotations structurelles, **24/24** contrastes positifs; **9** négatifs restent acceptés, à la limite autorisée.
- La CI [500 cas #42957398525](https://github.com/leye0/seman2/actions/runs/42957398525) est verte : **475/500** contre **474/500** sur la base; comparaison des artefacts `per_sentence.jsonl` ligne à ligne, même cohorte et même `case_id`/SHA : **seul l'index 96** passe de `roots_without_valid_analysis` à `complete`. Aucun autre statut, drapeau de dépassement de forêt ou de k-best, ni `root_rule` ne change. Les budgets restent **50 000 / 500 000 / 10 s**.
- La file déterministe est mise à jour à **475** succès, `last_attempted_index=96`, **25** résidus; le **prochain cas est 105**. Les anciens diagnostics 8/64/94 demeurent non certifiés malgré les améliorations de découpage; il faut continuer à exiger les attaches correctes de rang 1.
- Vérification des PR : **32 fusionnées, 3 fermées sans fusion** (#3, #10, #12, recherches abandonnées), **aucune ouverte** après intégration de #35.

## Point vérifié le 11 novembre 2026

- Le cas **94** a été diagnostiqué avec WordNet 3.0 dans
  [l'Action 42952309195](https://github.com/leye0/seman2/actions/runs/42952309195).
  Le passage d'origine v2 est toujours **sans racine complète**
  (1 234 nœuds, 38 813 états, budgets non dépassés). Les deux
  prédicats séparés et la coordination simple passent, mais une
  incise participiale après `; and,` ne se compose pas. Des
  sondes révèlent aussi des rattachements fautifs de
  `me close to her shawl` et `so much trouble as to bring her home`
  même sur des phrases reconnues. Aucun changement grammatical :
  toujours **474/500**, 26 résidus. Le curseur est à 94 ;
  prochain cas déterministe **96**. Voir
  [`CASE_94_SHARED_SUBJECT_PARTICIPIAL_INCISE.md`](CASE_94_SHARED_SUBJECT_PARTICIPIAL_INCISE.md).
  Le script et son workflow manuel sont conservés pour une reprise
  ciblée sans relancer inutilement le diagnostic complet des 500.

- La PR [#34](https://github.com/leye0/seman2/pull/34) ajoute uniquement
  à la **segmentation prospective v2** la conservation d'une courte citation
  contenant deux phrases, suivie d'une coordination externe du même sujet.
  V1 reste figé et le corpus 500 SHA-pinné inchangé. L'audit WordNet 3.0 du
  cas 64 est reproductible : 29 tokens, forêt 758, 26 147 états partiels,
  31 tests ciblés validés et 7 sondes indépendantes. Un arbre complet existe,
  mais le rang 1 rattache mal `upon me`, `as if ...` et `Hah` ; **ce n'est
  pas une correction grammaticale**. Détails dans
  [`CASE_64_QUOTED_SHARED_SUBJECT.md`](CASE_64_QUOTED_SHARED_SUBJECT.md).
  CI [Layer 1 #42950713364](https://github.com/leye0/seman2/actions/runs/42950713364)
  verte (**604 tests**) et CI [500 cas #42950713423](https://github.com/leye0/seman2/actions/runs/42950713423)
  verte, **474/500**,
  sans régression. PR fusionnée. La PR historique #12 a été fermée sans
  fusion, comme convenu pour les PR abandonnées.

- La PR [#33](https://github.com/leye0/seman2/pull/33) a été
  fusionnée sur `main` : l'audit des voisins de la cohorte 500 utilise
  explicitement la segmentation v1, tandis que le découpage prospectif
  v2 demeure opt-in dans le corpus. Les deux CI sur la PR étaient vertes,
  avec **602 tests Layer 1** et un diagnostic des **500 cas** terminé.
  Aucun changement de grammaire, de budget ou de couverture n'est revendiqué.
- Le travail v2 le plus récent est dans
  [`SEMICOLON_V2_TREE_AUDIT.md`](SEMICOLON_V2_TREE_AUDIT.md) :
  sur les quatre passages #8/#94/#182/#194, **aucun arbre de rang 1
  n'est encore certifié grammaticalement**. #8 et #194 ont une
  structure nominale fautive; #94 et #182 n'ont pas de racine complète.
  #194 est de plus censuré par le budget.
- Une étude supplémentaire du cas **64** a établi sa provenance entre
  deux unités d'un dialogue de Dickens : le sujet explicite du
  prédicat coordonné se trouve dans la phrase précédente. Voir
  [`CASE_64_QUOTED_SHARED_SUBJECT.md`](CASE_64_QUOTED_SHARED_SUBJECT.md).
  **Grammaire non corrigée** ; l'étude du cas 64 a été effectuée et
  documentée sans certification du rang 1. Depuis, le cas 94 a lui
  aussi été étudié et demeure non résolu. La file indique maintenant
  **96** comme prochain index ; 8, 64 et 94 restent parmi les 26 résidus.
- Pour les anomalies d'accord P2, les 16 alternatives marquées des
  cas #463 et #480 ne montrent chacune qu'un motif distinct de liens
  grammaticaux, sans solution stricte complète dans la recherche bornée.
  Voir [`REJECTION_TRACE_PROBE.md`](REJECTION_TRACE_PROBE.md).
  Cela ne prouve pas l'absence d'autres structures.

## Historique de la file (2026-11-08, après le diagnostic 8)

- À cette date le prochain cas était **64** selon
  [`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json) ; la file actualisée
  au 11 novembre reste à **474** succès, avec `last_attempted_index=94`
  et **96** comme prochain cas déterministe.
- **8** : « which I accordingly did. » est une relative supplémentaire
  **séparée de son antécédent par le découpage conservé au point-virgule**.
  Sans son contexte, elle n'est pas une clause indépendante ; lorsqu'on
  fournit artificiellement le contexte, le meilleur arbre rattache
  incorrectement la relative à `them` comme apposition nominale. Ne pas
  confondre cette fausse complétion avec une correction ; voir
  [`CASE_8_SEMICOLON_RELATIVE_CONTINUATION.md`](CASE_8_SEMICOLON_RELATIVE_CONTINUATION.md).
- **497** : deux tentatives de composition d'un complément nominal rectificatif
  « rather, indeed, of ... » ont reconnu la citation mais sélectionnaient
  un rattachement fautif de « at the irreverence of his words » à la
  proposition principale, et faisaient échouer le témoin **359**.
  Elles ont été retirées ; voir
  [`CASE_497_CORRECTIVE_NOMINAL_COMPLEMENT.md`](CASE_497_CORRECTIVE_NOMINAL_COMPLEMENT.md).
  Après restauration, CI de grammaire
  [42554373845](https://github.com/leye0/seman2/actions/runs/42554373845)
  et de dialogues
  [42554374055](https://github.com/leye0/seman2/actions/runs/42554374055)
  toutes deux **vertes**.
- **487** : diagnostic d'une proposition temporelle antéposée non reconnue
  puis saturation de la forêt globale ; voir
  [`CASE_487_RESOURCE_CENSORED_COORDINATION.md`](CASE_487_RESOURCE_CENSORED_COORDINATION.md).
- **491** : plusieurs analyses trompeuses (concession « for all that »,
  participiale passive « being both shot and drowned ») et une relative
  locative non reconnue ; voir
  [`CASE_491_CONCESSIVE_PASSIVE_RELATIVE.md`](CASE_491_CONCESSIVE_PASSIVE_RELATIVE.md).
- Ces cas restent **non résolus** : aucune règle grammaticale de ces
  tentatives n'est conservée, aucune augmentation du score ne doit être revendiquée. CI ciblées
  [487](https://github.com/leye0/seman2/actions/runs/42544413611) et
  [491](https://github.com/leye0/seman2/actions/runs/42552398902) et
  [8](https://github.com/leye0/seman2/actions/runs/42558920460) vertes.
  Le contrôle exhaustif du code de la PR #34 confirme **474/500**,
  avec la même cohorte historique ; les recherches prospectives v2 ne
  modifient pas ce score.

## Ce que nous construisons

Un **Layer 1 grammatical anglais symbolique** qui préserve toutes les lectures / sous-types lexicaux, les mots, leurs spans, traits, règles, variantes et sorties syntaxiques pour un Layer 2 futur. Nous développons la couverture et la correction sur phrases de romans, dialogues, accords et cas lourds. **Le Layer 2 cognitif, les anciens moteurs de coref/discours et les prototypes de snapping ne font pas partie du code présent.**

Le propriétaire a explicitement demandé de **cesser pour le moment les optimisations avec de nouvelles approches et patterns**. Ne pas réintroduire d'anciens algorithmes ou recommencer les mêmes benchmarks sans demande.

## Chemin actuel — ne pas s'y tromper

- **Défaut :** `seman_parser.engine.Parser(resources)` → `segmentation.build_lattice` → `vector_chart.VectorGrammar` → `_VectorForest` → `_LazyMaterializer`.
- **Opt-in pour phrases complexes :** `Parser(resources, complexity_policy=ComplexityPolicy(rule_start_threshold=...,min_tokens=17))` → `complexity_routing.StructuralRiskRouter` AVANT parse. Si phrase courte ou score insuffisant : le **même canonique**. Sinon : `vector_chart.VectorGrammar(lazy_trie_recognition=True)` → `lazy_trie_forest.LazySharedTrieForest` utilisant `shared_trie_forest.TrieRecognitionBase`, avec le **même k-best**.
- **Dialogues/guillemets :** grammaire de dialogue séparée conservée, jamais confiée au trie tant que non certifié.
- `shared_trie_forest.py` est une **base du trie lazy**, pas un mode alternatif eager.
- **Seule stratégie lourde exposée : `trie`**. `online`, `flat`, `indexed`, `shared_trie_recognition`, `early_lexical_filter`, `cache_boundaries` sont supprimés. Ne pas chercher ou ajouter ces options.

## Exécution et tests EXACTS

Lire et exécuter la section « Exécution depuis la racine » de `docs/RUN_CURRENT_LAYER1.md`. La CI `.github/workflows/core-seman2-validation.yml` télécharge WordNet 3.0, exécute les tests **réels** puis `python -m scripts.smoke_layer1`. Pour accéder au `WORDNET_DICT` hors CI, utiliser un répertoire de dictionnaire WordNet 3.0 `dict`.

```bash
WORDNET_DICT=/chemin/wordnet3/dict PYTHONPATH=superparser python -m scripts.smoke_layer1
```

Après chaque modification : tester le chemin canonique, le chemin trie configuré, les dialogues, le contrat d'output, les guillemets et la morphosyntaxe. **Un changement de nombre d'arbres, de mots, de traits ou de budget n'est pas automatiquement un gain.** Ne pas traiter les forêts saturées comme une validation complète.

## Données protégées

Les quatre romans nettoyés sont dans `superparser/research/verbnet_lr/corpora/`; leur manifeste et les guillemets sont préservés. `superparser/data/` et `data/` sont conservés. Les fichiers de corpus Wikipédia mentionnés autrefois n'ont pas été identifiés parmi les fichiers suivis : ne pas prétendre les avoir supprimés ou les inventer.

## Historique à connaître, pas à exécuter

Le moteur adaptatif à préfixes partagés a démontré **−15,6 % de CPU** sur une cohorte de 128 phrases (Action [39177896708](https://github.com/leye0/seman2/actions/runs/39177896708)). Les alternatives `online`/`flat` et la variante `indexed` n'ont pas montré de gain net. Les caches de signatures de sous-arbres ont trouvé des correspondances rapides mais **aucune accélération supplémentaire mesurée** et comportaient des risques si l'on acceptait des formes sans revalider les traits. Les forêts saturées restent une incertitude de correction. Les scripts et sources de ces essais sont disponibles **uniquement dans la sauvegarde Git** [`archive/pre-simplification-2026-10-18`](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18) et dans les commits antérieurs.

Le dépôt courant a été nettoyé pour contenir uniquement le parseur grammatical retenu, ses tests de qualité, les données et un benchmark du chemin actif.

## Dernier jalon de correction (cas 480)

- Commit de code validé localement : `08a5aecef12457e72c97776380bfd6e200d04752` ; voir [`CASE_480_MARKED_REPORTED_DIALOGUE.md`](CASE_480_MARKED_REPORTED_DIALOGUE.md).
- Le cas **480** est un dialogue rapporté à deux incises dialectales (`says they` et `they says`). En mode explicite `allow_marked_deviations=True`, le meilleur arbre est entièrement structuré : thème `As for you`, adresse `Benjamin Gunn`, présentative `here's a musket`, puis liste nominale coordonnée elliptique, avec **deux écarts d'accord indépendants** et leurs offsets. En mode strict le cas reste incomplet et `intent=unknown` : aucune prétendue normalisation du dialecte.
- Les règles `SPEECH-TAG` ordinaires vérifient désormais les accords en nombre et en personne ; les écarts n'apparaissent que sous règles marquées avec provenance précise. Les deux ouvertures lexicalement typées de fragments préservent strictement le témoin de saturation **359** (arbre correct, **1472** nœuds / **48529** états).
- CI principale [42381648511](https://github.com/leye0/seman2/actions/runs/42381648511) et CI dialogue [42381648518](https://github.com/leye0/seman2/actions/runs/42381648518) **vertes**. Suite locale : **499 tests** réussis ; qualité **120/120**, contrastes **24/24**, faux négatifs acceptés encore **9/24** ; smoke vert. Cohorte stricte **474/500**, aucun nouveau changement de statut ou de budget. Les seuls changements par rapport à l'ancien snapshot du cas 463 sont les ajustements **466** et **473**, déjà établis au jalon précédent.
- Prochaine phrase déterministe selon `GRAMMAR_CASE_QUEUE.json` : **487**. Le cas **480** reste dans la file stricte pour une future discussion des usages marqués, sans inflation artificielle du score.

## Prochaine tâche SANS instruction supplémentaire

Améliorer la **couverture grammaticale et la justesse des analyses du Layer 1** sur les phrases qui échouent, en restant compatible avec les mots, traits, alternatives et les dialogues. Pour chaque phrase, **appliquer le protocole de correction** : inspecter l'arbre sélectionné et les rattachements exacts, faire des tests positifs ET négatifs, mesurer les régressions sur la cohorte figée et ne pas assouplir globalement des contraintes pour faire croire à des succès.

## Phrase de reprise

> « Continue Seman2 sur `main`. Lis `AGENTS.md`, `docs/RUN_CURRENT_LAYER1.md`, `docs/CURRENT_RESEARCH_HANDOFF.md` et, pour toute correction de phrase, `docs/GRAMMAR_CASE_FIX_PROTOCOL.md`. Seuls le canonique et le trie shared-prefix lazy opt-in existent, dialogues canoniques. Exécute `scripts.smoke_layer1` et la CI. N'ajoute pas d'anciennes approches : concentrons-nous sur l'analyse grammaticale actuelle, sa correction et sa couverture. »
