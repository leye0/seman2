# Cinq analyses littéraires difficiles : contexte et causes distinctes

Contexte : cohorte fixe et **immuable** de 500 phrases, SHA-256
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
Indices zéro-basés 8, 76, 80, 96 et 100. Ce document ne modifie
ni l'extraction, ni les textes, ni les jugements de complétion.

Audit des paragraphes originaux :
[GitHub Actions, cinq cas et arbres complets](https://github.com/leye0/seman2/actions/runs/39705218103).
La provenance du contexte est produite par
`superparser/scripts/audit_context_dependencies.py` et les analyses
par l'unique interface publique `Parser.parse`.

## 8 — relative continuative après point-virgule

Unité extraite : `which I accordingly did.`

Source réelle :
`I could do no less, under these circumstances, than make Mr. Micawber
known to Uriah Heep and his mother; which I accordingly did.`

L'unité seule est `no_structural_root`. La phrase entière est
techniquement reconnue (`clause_comma`), **mais son meilleur arbre
est faux** : il associe `which I accordingly did` à
`his mother` via `np_appos_comma`, interprète `than make`
comme `PP`, et perd la structure de contrôle de `do no less than`.
**Ne pas compter cette reconnaissance hors contexte comme un succès
grammatical.** La solution cible est une relative continuative à
antécédent propositionnel, avec référence à l'événement du membre
précédent et ellipse de `do`, et non un ajout de CLAUSE autonome.

## 76 — nom substitut lexical et guillemets enchâssés

Unité : `Old what’s-his-name’s in a bad way, and it’s about that, I believe.’`

Le premier apostrophe est **interne à l'expression**
`what’s-his-name`; le dernier `’s` de `name’s` est une
copule indépendante. L'entrée nominale lexicalisée
`person-name-placeholder` est ajoutée à `syntax_lexicon.jsonl`.
Une projection lexicale sur l'ensemble de l'expression est disponible,
sans changer la tokenisation ni les autres catégories. Le statut passe
de `no_structural_root` à `complete` avec cette correction.

Le paragraphe précédent possède des niveaux de citation déjà ouverts :
`‘Why, from your old nurse,’ ... “‘J. Steerforth ...`.
L'unité fermante n'est donc pas une preuve de guillemet simplement
disparu : le balancement quote-scoped ajoute les marques manquantes
pour le contexte local, mais conserve le texte original séparément.

L'analyse structurale de `it’s about that` reste un point délicat.
La correction générale qui supprimait toutes les lectures ouvertes
du `s` après apostrophe donnait un meilleur arbre ici, mais
déclassait quatre reconnaissances antérieures (#99, #212, #441,
#466 : formes possessives et clitiques). Cette restriction a été
**revertée**. Le sens du mot `s` isolé ne doit pas être confondu
avec l'usage clitique, sans pour autant détruire des constructions
possessives que la grammaire actuelle ne sait pas encore composer.

## 80 — fermeture d'une citation à cheval sur un point-virgule

La phrase d'origine est la deuxième partie de :
`It is my intention, my dear Copperfield, to educate my son for
the Church; I will not deny that I should be happy, on his account,
to attain to eminence.’`

Le guillemet ouvrant `‘` a été hérité de la conversation précédente
et **est bien présent dans** `balanced_analysis_text`. L'échec
`roots_without_valid_analysis` subsiste, même avec ce rétablissement :
il faut corriger les rattachements des incises et des infinitives,
pas rejeter les guillemets du corpus.

## 96 — stage-cutch et tiret long

`stage-cutch` dispose **déjà** d'une lecture de nom
`stagecoach` sur tout le segment. La graphie `--` est **déjà**
une seule arête de `DASH` et, alternativement, de `COMMA`.
Les signes `-` individuels que l'on voit dans le rapport de
tokenisation ne prouvent donc aucune lacune lexicale.

Le segment `to--wherever it is` relève de la frontière
d'interruption et d'une relative libre locative. La grammaire
doit construire cette relation, sans doubler la normalisation
orthographique existante.

## 100 — relative objet zéro, sans mot inconnu

`handkerchiefs` est reconnu comme `N` pluriel, lemme
`handkerchief`, et `waved` porte une lecture verbale transitive.
**Rectification après tests minimaux sur `92151fa` :** la relative zéro
existe déjà (`wh_bare` + `vp_gap_transitive` + `np_relative_obj`).
`I saw the handkerchiefs they waved.` et le second membre entier sont
reconnus avec cette structure. Le blocage isolé est `I had barely time
to get down again` : l'adverbe entre HAVE possessif et NP manquait dans
le cadre avec infinitif. L'ajout de ce cadre permet maintenant la
reconnaissance du cas 100, sans nouvelle règle de relative.

**Qualité encore imparfaite :** le meilleur arbre traite `before the
coach started` comme PP + NP participial au lieu d'une subordonnée
finie. Le statut `complete` n'est donc pas une certification de
l'arbre entier. Voir `RESIDUAL_CONSTRUCTIONS_2026_10_21.md`.

## Règle méthodologique

Une phrase marquée `complete` n'est pas automatiquement un arbre
correct; un point-virgule ou un guillemet hérité n'est pas
automatiquement un échec du découpage. Les preuves conservent
l'original, la version balancée, le treillis lexical et l'arbre
sélectionné, et les nouvelles règles passent par des tests appariés
sans augmenter arbitrairement leurs scores.

## Mise à jour : cas 80

Les tests minimaux isolent trois pièces : complément infinitif de
l'adjectif sous copule de base, incise PP entre l'adjectif et TO,
et emploi prépositionnel `attain to`. Les nouvelles lectures/règles
licenciées permettent le cas canonique entier, avec les guillemets
transférés intacts. Le meilleur arbre conserve l'incise et le vrai
VP infinitif. Aucun score existant n'a été augmenté.
