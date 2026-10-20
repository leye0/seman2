# Supplément lexical littéraire du Layer 1

**Objectif :** compléter WordNet, non le remplacer. `superparser/data/literary_lexicon.jsonl` énumère **111 graphies attestées** (mots composés, dialecte, graphies anciennes ou contractées) avec `category`, `features`, `lemma`, `ebook_id`, `attested_surface` et `register`. Le moteur charge ce fichier après `syntax_lexicon.jsonl` via `ParserResources.from_dir` sans modifier son API `Parser.parse`. Chaque hypothèse du treillis conserve la forme originale dans `surface` et une provenance de sens `attested-literary-supplement`.

## Politique linguistique

- Le **tiret simple intralexical** de `blood-stained`, `shoulder-blade`, `pick-axe` est bien une partie du mot. Les entrées sont des hypothèses lexicales couvrant toute la graphie, en parallèle de ses éventuelles analyses compositionnelles.
- `--` dans `Anderson's ball--for it was Job--had ...` est **un tiret cadratin**, non un caractère lexical interne. Le treillis garde l'hypothèse `DASH` et sa compatibilité historique `COMMA`; aucun dictionnaire de composés ne peut le capturer comme mot.
- Les **graphies dialectales** `unfort'nate → unfortunate`, `sperrits → spirit`, `babby → baby`, `cap'n → captain`, `howsomever → however` ont une attestation littéraire et une catégorie justifiée, non un suffixe deviné arbitrairement. La graphie historique reste intacte dans le texte et les offsets.
- Ces textes sont de l'**anglais littéraire moderne du XIXe siècle** avec usages historiques et régionaux, non de l'Old English anglo-saxon. La catégorie grammaticale de chaque forme doit être attestée par son contexte, et toute polysémie documentée doit survivre dans les hypothèses alternatives.
- L'analyse compositionnelle productive `_hyphenated_candidates` demeure le **repli pour les nouveaux composés** qui ne se trouvent ni dans WordNet ni dans le supplément. Elle ne doit pas inventer un verbe sur la seule base d'un nom/adjectif constituant (ex. `bright-eyed`). Aucun mot inconnu n'est ajouté automatiquement au dictionnaire permanent : il faut d'abord valider sa réalité, sa catégorie et sa provenance.

## Origine et entretien

- **Treasure Island** (GITenberg `120.txt`, version épinglée dans `corpora/manifest.json`, git blob `5489be98377a7b4bac93b55bfb518d17cae6e68b`). Pour les formes composées et les graphies dialectales de cette édition.
- **Frankenstein** (GITenberg `84.txt`, git blob `176b1be39b6d925277c2d3bf413959a5dae8f095`). Pour les composés littéraires de cette édition.
- **David Copperfield** (GITenberg `766-0.txt`, git blob `4c3abb9f7d3a7e14e4675584bfecfbd66b032b4d`). Pour `carpet-bag`, `bright-eyed`, `stage-cutch` et la graphie `porkypine`.

Le fichier annoté est versionné comme **inventaire de formes attestées**, et non comme dictionnaire exhaustif de l'anglais : ajouter une entrée lorsqu'un nouveau mot est confirmé dans le corpus ou dans une source lexicographique. Ne pas effacer un éventuel sens WordNet, ni remplacer une langue dialectale dans la source.

Un catalogue lexical distinct est préférable à des règles de syntaxe par phrase : une seule hypothèse `ADJ blood-stained` est réutilisable avec n'importe quel nom compatible. Les tests `LiteraryExceptionDictionaryTests` garantissent formes, catégorie, nombre, provenance, relation avec le WordNet, et distinction entre `-` et `--`.

Le SHA de la cohorte fixe des 500 textes originaux ne doit pas changer.

## Audit reproductible de la couverture du supplément

Pour connaître **tous les composés encore absents du catalogue explicitement attesté**, lancer `PYTHONPATH=superparser python -m scripts.audit_literary_lexicon --top 50`. Cet audit parcourt les **quatre romans nettoyés épinglés** (pas les mentions Gutenberg légales) et fournit le nombre de types/occurrences par livre, la part listée et une file de révision classée par fréquence. Il exclut `--` (tiret cadratin) des composés.

**Attention :** les mots non listés ne sont pas nécessairement inconnus du parseur, car WordNet et l'assemblage productif des composés restent actifs. Inversement, une graphie réellement attestée ne garantit pas que sa catégorie grammaticale soit inférable sans vérification humaine. L'audit sert à enrichir le dictionnaire progressivement sans polluer les analyses avec des sens inventés.

## Contrôle de qualité des arbres à la suite de la mise en place du lexique (octobre 2026)

Après intégration de 86 formes attestées, la mesure officielle passe de **437 à 439/500 complétions brutes**, sur la même cohorte SHA et sans perte d'anciennes complétions ([CI 500](https://github.com/leye0/seman2/actions/runs/39449129137)). Cependant **ces deux nouvelles complétions ne sont PAS des gains syntaxiques certifiés** :

- **Index 109**, Dickens, graphies dialectales `babby` et `Porkypine`. La chaîne analysée comporte une accumulation de **six guillemets simples ouvrants synthétiques**, et le meilleur arbre fait faussement de `a babby fur` un groupe nominal composé puis de `you, in the form` une relative objet. Ce défaut mêle transfert de citation et rattachement syntaxique : **faux positif de couverture**, même si les graphies ont désormais de vrais sens dans le lexique.
- **Index 459**, Stevenson, `that's unfort'nate--appears as if killing parties was a waste of time.` : `unfort'nate` est correctement reconnu comme `ADJ` (véritable gain lexical) et `--` identifié dans le treillis. Toutefois le meilleur arbre traite `as if killing` comme un groupe prépositionnel et `parties was a waste of time` comme une indépendante, au lieu d'une construction `as if` correcte. **Faux positif de qualité syntaxique**.

Conclusion : **439/500 est un indicateur de reconnaissance structurelle brute, pas 439 arbres validés**. Le supplément est utile sur le plan lexical et ne modifie pas le corpus; les priorités restantes sont le balancement interphrastique des guillemets et l'analyse de `as if`. Pour confirmer ces conclusions, la CI de suivi audite explicitement les meilleurs arbres 109 et 459. Ne pas augmenter le score de qualité certifiée sur ces deux cas.


## Première vague priorisée par fréquence

L'audit des quatre romans a révélé 1 567 types de composés avec tiret simple, dont initialement 79 étaient déjà dans le catalogue explicite de 86 entrées. Nous avons ensuite ajouté **25 composés parmi les plus fréquents**, avec des catégories vérifiables : `drawing-room`, `child-wife`, `pocket-handkerchief`, `public-house`, `dining-room`, `stage-coach`, `good-natured`, `old-fashioned`, `business-like`, etc. Les variantes contextuellement polysémiques `good-bye` (nom et interjection) et `half-way` (adjectif/adverbe) conservent leurs deux lectures indépendantes. L'existence d'un composé seul n'autorise jamais à inventer un sens verbal.

Les graphies non encore inscrites dans ce dictionnaire explicite ne sont pas forcément inconnues du moteur : WordNet, les alias orthographiques comme `to-day` / `to-morrow` et le fallback compositionnel sont conservés. Les séquences idiomatiques telles que `a-going`, `half-an-hour` et `half-a-dozen` doivent recevoir une analyse morphosyntaxique avant ajout, plutôt qu'une fausse catégorie `N` par défaut.

## Priorité au mécanisme productif plutôt qu'au catalogue exhaustif

Le catalogue littéraire **ne doit pas devenir un dictionnaire complet des 1 567 types avec tiret**. Lorsque le mot se dérive de façon morphologiquement justifiée, le treillis construit directement une hypothèse couvrant le composé : `N-X` par tête nominale attestée, `X-ADJ` par tête adjectivale et, désormais, `X + V[participe passé]` comme adjectif composé (`river-washed`, `sun-painted`). La catégorie grammaticale et la flexion sont validées sur la forme écrite et les lectures WordNet du constituant. Le composé adjectival n'est pas transformé en verbe arbitraire.

Le fichier explicite reste utile **seulement** pour les graphies dialectales non déductibles (`babby`, `sperrits`, `unfort'nate`, `stage-cutch`), les irrégularités, et éventuellement les sens lexicalisés spécifiques. Même lorsqu'un mot y figure, la segmentation compositionnelle et les interprétations WordNet pertinentes doivent pouvoir coexister. Les tests `ProductiveHyphenMorphologyWithoutDictionaryTests` chargent volontairement le parseur **sans** `literary_lexicon.jsonl` pour démontrer la généralisation hors liste.
