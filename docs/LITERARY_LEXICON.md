# Supplément lexical littéraire du Layer 1

**Objectif :** compléter WordNet, non le remplacer. `superparser/data/literary_lexicon.jsonl` énumère **86 graphies attestées** (mots composés, dialecte, graphies anciennes ou contractées) avec `category`, `features`, `lemma`, `ebook_id`, `attested_surface` et `register`. Le moteur charge ce fichier après `syntax_lexicon.jsonl` via `ParserResources.from_dir` sans modifier son API `Parser.parse`. Chaque hypothèse du treillis conserve la forme originale dans `surface` et une provenance de sens `attested-literary-supplement`.

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
