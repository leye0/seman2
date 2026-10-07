# IND-02 — Inductive Logic Programming

Popper apprend en mode bruité une conjonction sur des prédicats anonymes du
Learned Graph. Les IDs `Pattern_...` sont mappés mécaniquement vers des atomes
Prolog minuscules, contrainte lexicale de Prolog/Clingo. Janus/SWI-Prolog
recalcule la couverture et NuWLS-c résout aussi un témoin MaxSAT indépendant.

Une seconde expérience Popper est générée depuis le treillis réel IND-01. La
cible est seulement l'identifiant anonyme d'un concept FCA; les prédicats du
background sont des IDs mécaniques mappés aux attributs du ledger HYP-04.
La cible FCA étant sans bruit, cette seconde expérience utilise le mode exact;
le mode bruité/NuWLS reste qualifié par l'oracle contrôlé. La règle apprise doit
retrouver exactement les hypothèses de l'extension selon un contre-calcul
indépendant et conserver leurs identifiants d'artefacts cognitifs. Ce test
vérifie la chaîne de données, pas encore une généralisation sur de nouveaux
épisodes.

```bash
./poc/ind-02/run.sh
```
