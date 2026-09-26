# NLP-01 — Analyse HPSG complète

Cette POC mesure les données grammaticales réellement émises par ACE 0.9.34
avec l'image ERG 2018 installée dans le dépôt. Elle ne teste ni MRS/EDS/DMRS en
détail (`NLP-02`), ni l'exhaustivité des ambiguïtés (`NLP-03`).

## Exécution

Depuis la racine du dépôt :

```bash
./poc/nlp-01/run.sh
```

La limite est configurable :

```bash
./poc/nlp-01/run.sh --max-results 20
```

Le script échoue si les dix constructions demandées ne sont plus couvertes, si
aucun échec explicite n'est observé, ou si une analyse positive ne contient pas
les champs essentiels. Il régénère :

- `output/raw/ace-tsdb.stdout` et `ace-tsdb.stderr` : sortie ACE brute ;
- `output/results.json` : extraction structurée, sans suppression des chaînes
  brutes ;
- `output/versions-and-parameters.json` : versions, empreinte de l'image ERG et
  paramètres.

## Résultat observé

**Verdict : GO, avec une limite importante sur la notion de « complète ».**

Avec la limite par défaut de 10, les lectures rendues sont : 2 déclaratives, 6
interrogatives, 2 impératives, 10 pour la négation (limite atteinte), 3 pour la
coordination, 4 pour la relative, 7 pour le contrôle, 3 pour le passif, 2 pour
le fragment et 0 pour la phrase non grammaticale.

ACE/ERG fournit bien, pour chaque entrée :

- le treillis de tokens initial et interne ; pour les tokens initiaux, la POC
  extrait l'identifiant, les sommets, le charspan, la forme, le POS et sa
  probabilité ;
- le nombre de lectures, dans la limite demandée, ainsi que les tailles du chart
  (`pedges`, `aedges`) ;
- pour chaque lecture, un identifiant ordinal, le rang de retour, le `:ascore`
  et la probabilité normalisée ;
- la dérivation HPSG (règles, entrées lexicales, scores, spans et traits de
  tokens), conservée brute et décodée en arbre ;
- un arbre syntaxique de constituants, brut et décodé ;
- les traits morphosyntaxiques portés par les variables MRS : notamment `SF`,
  `TENSE`, `MOOD`, `PROG`, `PERF`, `PERS`, `NUM` et `IND` lorsqu'ils sont
  instanciés ;
- les notes, avertissements et erreurs ACE ;
- un échec non ambigu : `status = parse_failure`, `analysis_count = 0`, une
  liste d'analyses vide et un objet `failure` explicite.

« Dérivation HPSG complète » ne signifie toutefois pas qu'ACE sérialise l'AVM
complète de chaque nœud de phrase. La sortie expose l'arbre de dérivation et les
traits lexicaux/token utiles, tandis que certains traits grammaticaux sont
observables indirectement dans la MRS. Une application exigeant toutes les
structures de traits internes devra employer une instrumentation plus profonde
de la grammaire ou d'ACE ; ces AVM absentes ne doivent pas être inventées par
l'adaptateur.

Le champ `limit_reached` indique seulement que le nombre rendu atteint la
limite configurée : dans ce cas, la POC ne prétend pas connaître le nombre total
de lectures. Le rang est l'ordre retourné par ACE, et non un identifiant stable
entre versions de la grammaire.
