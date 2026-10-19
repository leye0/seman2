# Seman2 — carnet de recherche sur les 500 phrases de romans

## Protocole

La cohorte est fixée par l'empreinte SHA-256 de `cohort.jsonl` :
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.

Chaque unité est analysée une fois, avec 50 000 états de reconnaissance,
500 000 unités de travail k-best et un plafond de 10 s par cas.
Ces unités k-best **ne sont pas** un comptage direct de combinaisons.
Pour chaque échec, le JSONL exporte les hypothèses lexicales, sous-types,
sens, provenances, traits, contraintes et candidats multi-mots.
`pattern_contrasts.json` compare les signatures parmi les succès et échecs.
Les archives GitHub Actions expirent après 90 jours ; le code et la
sélection demeurent reproductibles.

## Résultats mesurés sur la cohorte figée

| Expérience | Complètes | Remarques |
|---|---:|---|
| Baseline initiale | 316/500 (63,2 %) | Avant nouveaux correctifs |
| Guillemets typographiques et règles localisées | 330/500 (66 %) | Surtout dialogues Dickens |
| Ajout de lecture syntaxique de `--` / tiret long | 341/500 (68,2 %) | Reconnaissance de séquences ponctuées |
| Analyse contrastive et audit sous-tokens | 340/500 (68 %) | Une phrase longue a expiré différemment |
| Copule contractée `'re`, quantificateur `many` | 342/500 (68,4 %) | Exécution CI vérifiée |

Le nombre de timeouts est sensible à l'exécution Linux ; des variations
de 1–3 cas aux budgets de 10 s ne sont pas une preuve de régression
grammaticale. Les améliorations doivent être inspectées phrase par phrase,
et une racine complète ne prouve pas que le meilleur arbre soit correct.

## Changements effectivement intégrés à `main`

1. `vpnp_bare_coord` : coordination de prédicats impératifs à forme de base
   (« Come and see him. »). `vpnp_post_adv` : adverbe postverbal au sein
   d'un prédicat nu ; `clause_post_adv_comma` : adverbe détaché final
   (« Steerforth was considerate, too. »).
2. Reconnaissance des dialogues délimités par `‘…’`, distincts des
   apostrophes internes de `don’t`.
3. Un candidat de ponctuation couvrant tout `--`, `---`, `—` ou `–`,
   sans promouvoir un tiret simple au rang de virgule et sans modifier le
   corpus source.
4. Lexique fonctionnel : `'re` comme copule contractée et `many` comme
   pronom quantificateur pluriel / déterminant.
5. Diagnostic contrastif des bigrams et trigrams de catégories lexicales :
   fréquence dans les succès **et** dans les échecs, en excluant les
   budgets et délais non conclusifs.
6. Séparation entre mot sans candidat et token dont l'analyse passe par
   plusieurs sous-arêtes (possessifs et clitiques). Les graphies lexicales
   doivent correspondre à la source ; un nom `ai` suivi du clitique
   négatif `n't` ne démontre pas qu'une négation dialectale `ain't` soit
   correctement analysée.

Les poids de classement des impératifs ont été expérimentés puis **rétablis** :
le gain d'un exemple isolé changeait indûment les meilleurs arbres de phrases
non concernées. Des tests d'échec connu suivent ces ambiguïtés au lieu de
considérer tout arbre complet comme correct.

## Prochaines familles à investiguer avec rigueur

**Dialogues tronqués ou citations fragmentaires.** Plusieurs extraits
sélectionnés commencent avec une citation ouverte et finissent après une
attribution/reprise. Un fragment comme « ‘Come and prove it. » ne doit pas
être traité comme preuve d'une lacune du langage grammatical sans vérifier
le paragraphe original. Le texte d'origine et l'unité normalisée sont
conservés séparément.

**Questions, exclamations, vocatifs et ellipses.** Les exemples courts
non analysés doivent être répartis entre interrogative elliptique,
apostrophe/vocatif, NP isolé et clause finie, avec des contre-exemples.

**Compléments de l'adjectif.** La signature `ADJ + PREP` apparaissait dans
8 cas échoués et 0 cas réussis sur une campagne, mais les contextes
(« afraid of him », « aware of », « different from », « sorry for »)
comportent souvent d'autres dépendances. La règle
`adjp_adj_pp` existe déjà : ne pas créer un doublon ou un raccourci
permissif avant d'avoir isolé le premier sous-arbre réellement manquant.

**Contractions et négations historiques.** `ain't`, `unfort'nate`,
`I’ve`, `that's` et autres élisions demandent une analyse de la
morphologie et de leurs graphies historiques. `ain't` est du dialogue
vernaculaire, **pas** une phrase objectivement erronée. Ajouter une lecture
syntaxique motivée par la forme, non une règle générique permettant de
reclasser n'importe quel fragment comme auxiliaire.

**Arbres complets incorrects.** « Open the box and close it. » est un
impératif grammatical dont le meilleur arbre du parseur privilégie encore
une interprétation nominale improbable. Cette catégorie demande des
améliorations de préférence structurelle, pas seulement une augmentation du
pourcentage de couverture.

**Cas objectivement fautifs.** Ne jamais déduire qu'une phrase est erronée
du seul fait qu'elle échoue. Établir une catégorie explicite, révisable et
appuyée par l'extrait d'origine avant de retirer un cas des statistiques.
Les citations incomplètes produites par le segmentateur doivent être
corrigées au niveau de la segmentation ou évaluées comme fragments.

## Première personne du verbe *be*

L'inventaire préexistant contenait `is`, `are`, `was`, `were` mais pas la copule `am`, à l'origine d'absences de lecture COPULA dans plusieurs dialogues (`I am sure`, `am I not alone`). Ajout de lectures distinctes COPULA et AUX-BE, avec accord singulier première personne, afin de ne pas étendre incorrectement la catégorie à d'autres sujets.

## Négation non standard `ain't`

Quatre cas dans *Treasure Island* présentent la graphie dialectale `ain't`. C'est un auxiliaire/copule négatif vernaculaire attesté, pas une faute à exclure du corpus. Une entrée explicite `COPULA`/`AUX-BE` négative est ajoutée, ainsi qu'un modèle étroit de question-étiquette négative `ain't you?` et de prédicat adjectival négatif `He ain't ready.`. Les règles exigent le trait `negation=true`, afin de ne pas élargir l'analyse de toutes les copules.

## Apostrophes typographiques dans les contractions

Les formes avec U+2019 (don’t, I’ll, we’re, Peggotty’s) obtenaient des candidats lexicaux fragmentaires. Le treillis ajoute les sous-unités morphologiques à partir de la graphie normalisée, mais garde tous les offsets et les surfaces réels du texte original. La tokenisation ne change pas : l’empreinte de la cohorte de 500 phrases est préservée.

## Exclamations nominales et vocatives sans verbe

Une phrase littéraire peut être une exclamation complète en discours, sans verbe fini : par exemple « What a good, kind boy! » ou « Peace, peace! ». Introduction d'un terminal syntaxique EXCLMARK, offert en **plus** de l'ancienne lecture COMMA du point d'exclamation, puis de règles limitées par un vrai signe « ! ». La construction « what a ... » exige un déterminant indéfini et une lecture interrogative/exclamative du mot wh. Pas de règle universelle qui transforme n'importe quel NP en clause finie.

## Démonstratifs et quantificateurs pluriels

Les lectures lexicales classiques de « these », « those » et « both » manquaient comme DET/PRONOUN, empêchant ou compliquant les groupes nominaux « these questions » et « both these questions ». Ajout de lectures grammaticales plurielles explicites, sans règle syntaxique attrape-tout, avec tests de reconnaissance en contexte.

## Questions copulatives et interrogations elliptiques

Les questions dont le sujet suit une copule et celles où le prédicat est sous-entendu avaient une couverture incomplète. Ajout de productions exigeant explicitement QMARK pour les structures « Who are you? », « Is she ready? », « Is she a doctor? », « Did you? », « Can you? », « Did not you? » (ordre négatif ancien) et « Am I not alone? ». L’ellipse est marquée comme telle; aucune production interrogative sans point d'interrogation n’a été ajoutée.

## Gardes contre les faux positifs dans l'ellipse auxiliaire

L'ajout de pronoms/déterminants pluriels a révélé qu'une ancienne règle `clause_np_coord_aux_adv` acceptait une combinaison arbitraire NP + VP-NP, y compris l'agrammatical « Those child are sleeping ». Elle exige maintenant explicitement le trait `ellipsis=true`, produit uniquement pour `AUX ADV` dans `vp_aux_adv` (« John did too »). Les interrogatives copulatives, déjà limitées aux phrases terminées par QMARK, préfèrent un vrai prédicat adjectival aux homographes nominaux; le prédicat nominal reste disponible lorsqu'il est grammatical.

## Accord des noms à déterminant temporel

La règle héritée `np_temporal` (DET N) acceptait un déterminant pluriel avec un nom singulier car elle ne contrôlait que le nombre du nom. Elle produisait ainsi une fausse lecture de « Those child are sleeping », classée comme NP temporel (!). Le trait de nombre est maintenant unifié entre DET et N pour toute construction `np_temporal`. Cela élimine une cause véritable d'acceptation de phrases grammaticalement fautives, au lieu de supprimer la catégorie plurielle correcte de « those ».

## Harmonisation du nombre à travers neuf autres règles nominales

Un audit de toutes les productions NP comprenant DET et N révèle neuf variantes où le nombre n'était vérifié que sur le nom (adjectifs, deux déterminants, adverbes, compléments en of, relative, participiale, etc.). Dans chaque variante, tous les DET du groupe sont maintenant unifiés avec le nombre du nom (variable `?n`). Les déterminants postposés distributifs (comme « the children each ») sont **exclus** de cette contrainte, car leur nombre peut légitimement différer.

## Contrôle de la segmentation des citations

Le diagnostic réexamine en seconde passe uniquement les phrases sans racine syntaxique contenant une citation ouvrante sans fermeture. Une proposition de fermeture est ajoutée **dans l'unité d'analyse expérimentale**, jamais dans le texte Gutenberg et jamais dans les 500 cas de référence. Les résultats appariés sont exportés dans `quote_repair_trials.jsonl` et résumés séparément des 500 diagnostics bruts. Une réussite après ajout d'un guillemet n'est pas une preuve de bonne segmentation contextuelle, mais isole un facteur d'échec transversal.

## Citations ASCII simples et faux guillemets possessifs

L'overlay de dialogue reconnaît les citations ASCII simples `'Who are you?'` en plus des guillemets doubles et typographiques, sans convertir les apostrophes intérieures de `don't`, `John's` ou `M'Graw` en frontières. Le protocole expérimental de fermeture des guillemets ne réparera plus à tort un apostrophe possessive finale (`minutes' conversation`) ni un guillemet fermant orphelin après la ponctuation.
