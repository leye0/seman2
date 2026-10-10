# Seman2 — refactoring expérimental des signatures grammaticales (v1)

Cible : dépôt privé `leye0/seman2`, dossier `superparser`, branche `main` telle qu'inspectée le 10 octobre 2026.

**Ce ZIP contient du code exécutable, une installation conservatrice, des tests, et un benchmark.** Il ne remplace pas sans validation le parseur historique. Son rôle est de prouver une nouvelle représentation en minimisant les risques de régression.

## Ce qui est effectivement implémenté

1. `CachedLexiconView` : cache LRU borné **par surface** pour `lookup_morphology`, utile même lorsque les phrases sont nouvelles, sans modifier WordNet.
2. `LexicalSignatureLattice` : **un masque de bits par span lexical** ; toutes les catégories `N | V | ...` sont gardées sans produit cartésien. Les multi-mots et contractions possèdent des spans distincts.
3. `ConstructionIndex` : compilation des motifs connus en **trie** et matching de l'ensemble des catégories lexicales avec un NFA de paires `(état, début)`. Les expressions reconnues servent d'**indices**, jamais de preuves syntaxiques.
4. `EarleyStructureRecognizer` : reconnaisseur prédictif **hiérarchique** de toutes les règles compilées, avec états `(règle, point, origine, position)` partagés ; sans contraintes de traits ni sémantique. C’est un test nécessaire de structure, et non une preuve de validité.
5. `ConstructionLearner` : observe les vraies analyses du `Chart`, compte les motifs grammaticaux récurrents, et promeut les motifs fréquents dans l'index **mais pas dans la grammaire**. Les suites inconnues sont mises en quarantaine sous forme de signatures de catégories.
6. `FastParser` : sous-classe opt-in du `Parser` existant qui conserve `parse()` et donne `signature_lattice()`, `scan_constructions()`, `observe()` et `parse_with_scan()`.
7. Correctif de `chart.py` à l'installation : **provenances récursives différées** jusqu'à `as_dict()`/accès aux enfants. Les enfants réels sont toujours conservés dans le chart. Aucun plafond d'ambiguïté n'est modifié.
8. Correctif **optionnel** de `lexicon.py` : les catégories WordNet ne sont plus masquées par un mot déjà présent dans le lexique fermé. À tester séparément : cela peut *augmenter* le nombre d'analyses.

## Installer

Depuis la racine de l'archive extraite :

```bash
python apply_refactor.py /chemin/vers/seman2/superparser --dry-run
python apply_refactor.py /chemin/vers/seman2/superparser
cd /chemin/vers/seman2/superparser
python -m unittest discover -s tests -p 'test_fastpath.py' -v
```

Les fichiers d'origine sont sauvegardés sous `superparser/.fastpath_backup/<horodatage>/`. Rien n'est publié ni modifié dans GitHub. Le script est idempotent, vérifie l'exactitude des points d'insertion et refuse une version inattendue de `chart.py`.

**Option séparée** : `python apply_refactor.py /chemin/vers/seman2/superparser --merge-wordnet` corrige le masquage des catégories WordNet, mais modifie la couverture et potentiellement les performances. Ne pas le faire pendant le benchmark initial.

## Utilisation

```python
from seman_parser.fastpath import FastParser

parser = FastParser.from_dir('data', cache_size=0)

sig = parser.signature_lattice('The man is breaking the hammer.')
for token in sig.token_signatures:
    print(token.surface, token.categories, bin(token.mask))

# Indications structurelles rapides, pas un remplacement du parseur.
known = parser.scan_constructions('The man is breaking the hammer.')
print(known)
structural = parser.recognize_structure('The man is breaking the hammer.')
print(structural.possible, structural.state_count)

# La qualité grammaticale reste celle du parseur de référence.
report = parser.parse('The man is breaking the hammer.')
parser.observe(report)   # Apprentissage explicite, facultatif.
print(parser.learner.stats())

# Construction hypothétique explicitement ajoutée à l'index de motifs.
from seman_parser.fastpath import ConstructionTemplate
parser.constructions.add(ConstructionTemplate(
    label='CLAUSE',
    categories=('DET', 'N', 'AUX', 'V', 'DET', 'N'),
    source='hypothesis',
))
print(parser.scan_constructions('The man is breaking the hammer.'))
```

**Important :** un motif reconnu ne signifie pas que l'accord, les rôles, les dépendances ou la composition sémantique sont corrects. Le vrai `Chart` reste l'oracle. De même, une absence de motif connu ne veut pas dire que la phrase est invalide.

## Mesurer avant / après sur 850 phrases

Pour mesurer le refactoring **sans changer le protocole**, lancer d'abord la baseline avant installation :

```bash
python scripts/bench_fastpath.py /chemin/vers/seman2/superparser \
  --mode baseline --limit 850 --output before.json
```

Après l'installation :

```bash
python scripts/bench_fastpath.py /chemin/vers/seman2/superparser \
  --mode fast --limit 850 --output after.json --compare before.json
python scripts/bench_fastpath.py /chemin/vers/seman2/superparser \
  --mode scan --limit 850 --output scan_only.json
python scripts/bench_fastpath.py /chemin/vers/seman2/superparser \
  --mode recognize --limit 850 --output earley_recognizer.json
```

Le benchmark isole les temps d'une phrase avec WordNet déjà chargé et le parseur réutilisé ; la période de warmup n'est pas comptée. Il écrit médiane, p90, p95, p99, max, statut, catégorie, règle gagnante, traits, relations normalisées et nombre d'analyses racines.

La comparaison `--compare` vérifie notamment les **alternatives racines**. Une divergence ne doit pas être ignorée. Le score / ordre d'analyses et l'intégralité de la forêt peuvent également nécessiter des tests plus stricts avant déploiement.

## État de la recherche — limitations assumées

- La couche de vecteurs + trie est un **fast scan de motifs réutilisables**. Un reconnaisseur prédictif Earley simplifié est également inclus, mais ni l’un ni l’autre ne remplace encore une forêt SPPF complète avec unification.
- `FastParser.parse()` continue de faire tourner le **chart original**. Le gain sur la latence *totale* vient pour l'instant du cache morphologique et de la provenance paresseuse, à mesurer. Les deux scanners peuvent être plus rapides que le parsing complet, mais ils ne produisent pas les mêmes résultats ni les mêmes garanties.
- Les motifs de `ConstructionIndex` sont pour l'instant des suites **plates** de catégories ; ils ne suffisent pas à représenter les contraintes syntaxiques de longues phrases.
- Les motifs automatiquement observés ne sont pas ajoutés à `grammar.jsonl`. Il faudrait des oracles positifs/négatifs avant de promouvoir une construction en règle grammaticale.
- Aucune garantie de 5 ms par phrase : l'objectif est de quantifier le goulot d'étranglement et construire une base saine pour un reconnaisseur partagé ultérieur.
- Le budget actuel de deux variantes par état partiel **n'est pas modifié** : il peut toujours sacrifier des interprétations. Le prochain jalon scientifique est une forêt réellement partagée par interfaces de contraintes compatibles.
- Si les ressources apprises changent, appeler `invalidate_knowledge_caches()` ; pour des changements grammaticaux, recréer `FastParser` (et son index de construction).

## Prochain refactoring substantiel

Après validation de cette couche :
1. Compiler les règles vers des états de prédiction Left-Corner/Earley.
2. Partager l'exécution par **état grammatical + interface de traits**, indépendamment du nombre de dérivations.
3. Rendre également différée la composition des graphes sémantiques, avec identifiants et bindings stables.
4. Comparer systématiquement les structures et rôles conservés, et pas seulement la couverture.

C'est à cette étape que l'on pourrait espérer un changement d'ordre de grandeur de la latence totale sans perdre l'ambiguïté.
