# État de référence inspecté

Sources (GitHub connecté, dépôt privé `leye0/seman2`, branche `main`, 10 octobre 2026) :

- `superparser/seman_parser/chart.py` — blob `93ab0e374c5185b411eb88dfe9be2192ef7e5d79`
- `superparser/seman_parser/lexicon.py` — blob `f4deeec9819e063c4e9f60cd4ebe3c2f0ead0627`

Points d'insertion du patch contrôlés contre les fichiers du dépôt : correspondance unique de la déclaration `Provenance`, de son sérialiseur, de l'expansion récursive des provenances, et du retour anticipé du lexique statique (patch WordNet facultatif).

## Tests exécutés pendant la préparation

- Compilation Python (`py_compile`) des nouveaux modules : OK.
- Installation `--dry-run` et réelle sur un *checkout factice* reproduisant les signatures des points de patch : OK.
- 10 tests unitaires sur ce checkout factice : OK. Ces tests portent sur bitmasks, ambiguïtés, matching, Earley, multisurfaces, apprentissage prudent, cache et provenance différée.

## Non vérifié ici

- Les 850 phrases n'ont **pas** été réexécutées dans l'environnement d'origine. Le dépôt est privé, accessible par connecteur de lecture mais son environnement WordNet et les corpus d'exécution ne sont pas montés localement dans cette session.
- Le gain du refactoring sur la latence **du parseur complet** n'est pas mesuré. L'algorithme de reconnaissance seul est distinct du résultat complet.
- La compatibilité fonctionnelle exhaustive et la conservation de la totalité des ambiguïtés sont à vérifier via les tests du vrai dépôt et des oracles plus riches que la comparaison des racines.

Ce document est volontairement explicite pour éviter de confondre un prototype prêt à tester avec une optimisation de production déjà validée.
