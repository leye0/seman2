# Dépendances actives et candidats d'admission

L'architecture active est `plans/architecture_cognitive_developpementale.md`.
Une bibliothèque installée n'est pas automatiquement une dépendance du système.

## Socle minimal autorisé

| Besoin architectural | Outil | Rôle strict |
|---|---|---|
| grammaire formelle anglaise | ACE + ERG + PyDelphin | produire HPSG/MRS/EDS/DMRS et leurs alternatives pour L1 |
| contraintes relationnelles et temporelles | Z3 | vérifier une famille de contraintes; ne décide pas la vérité |
| exécution cognitive | Soar + SML | buts, opérateurs, impasses et foyer de travail borné |
| formes distribuées | NumPy | opérations vectorielles explicites et reproductibles |
| stockage/checkpoint | bibliothèque standard, JSON canonique; Arrow/Parquet seulement si la charge l'exige | persistance et audit extérieurs à la cognition |
| réalisation anglaise | SimpleNLG | réaliser un plan L6; ne choisit pas le contenu |
| évaluation externe | OpenRouter | noter des probes selon une rubrique figée; aucun accès en écriture au runtime |

ACE/ERG/PyDelphin sont nécessaires dès SYS-01. Z3, Soar et SimpleNLG ne sont
admis dans le chemin actif qu'aux POC SYS-05, SYS-07 et SYS-10 respectivement.

## Outils disponibles mais non admis

Link Grammar, Dynamic Syntax/DyLan, WordNet, VerbNet, PropBank, FrameNet,
SemLink, SUMO, HeidelTime, Duckling, Epitran, PanPhon, Pynini/OpenFst,
Phonetisaurus, IsaNLP RST, CoreNLP, Coreferee, ConvoKit, Popper, FCA et les
autres outils de l'ancien système peuvent rester installés. Ils n'appartiennent
pas au runtime actif.

Un de ces outils n'est réintroduit que si une ablation sur une POC `SYS-*` :

1. consomme les mêmes artefacts réels;
2. améliore une gate tenue à l'écart;
3. conserve ambiguïtés et provenance;
4. n'impose pas une ontologie ou une mémoire parallèle;
5. respecte les budgets RAM, latence et maintenance;
6. démontre une contribution utilisée par l'étage supérieur.

À défaut, il reste une référence archivée ou est retiré. Les banques lexicales
ne sont jamais des mémoires initiales : si leur contenu doit éduquer un modèle,
il est ingéré comme expérience ordinaire.

## Données actives

- `data/the_map_of_everything_nlp_novel.txt` : curriculum léger initial;
- `data/english-dictionary.jsonl` : corpus lexicographique optionnel, ingéré par
  la chaîne normale;
- les Parquet : sources d'expériences ultérieures, jamais interfaces des
  systèmes haut niveau.

Les versions installées et recettes historiques sont conservées dans
`archives/ancien_systeme/plans/required_libraries.md`. Ce fichier historique
n'accorde aucun statut actif à ces outils.
