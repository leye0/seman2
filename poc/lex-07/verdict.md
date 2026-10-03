# Verdict LEX-07

## Décision

La pile convient pour construire un ensemble de candidats traçable lié à une
occurrence. Elle ne fournit pas, par simple composition des ressources, un
désambiguïsateur lexical ou un détecteur de frame.

Sur quatre occurrences et dix analyses ERG :

- `run` produit 41 candidats WordNet, 4 VerbNet, 9 PropBank et 8 FrameNet par
  occurrence ;
- `bank` produit 10 candidats WordNet et 2 FrameNet par occurrence ;
- les arêtes cumulées (lookups répétés pour les contrastes) sont 14
  VerbNet→WordNet, 16 PropBank→VerbNet, 22 VerbNet→FrameNet et 102
  WordNet→SUMO ;
- 38 concepts SUMO distincts sont atteints ;
- zéro candidat, sens, frame ou rôle sémantique est sélectionné.

## Ce qui est observé

ACE/ERG fournit l'ancre, le lemme/POS dérivé du prédicat et la structure MRS.
Les quatre ressources lexicales fournissent ensuite des listes par lemme/POS.
Les membres VerbNet, SemLink et WordNet–SUMO fournissent des arêtes typées entre
candidats. Les concepts SUMO sont seulement les extrémités des mappings
WordNet ; ils ne deviennent pas des concepts internes.

Le contraste `run` prouve que le contexte syntaxico-sémantique apporte une
information exploitable : `The athlete ran to the station` expose `ARG1`,
tandis que `The engineer ran the program` expose `ARG1` et `ARG2`. Cette
information ne suffit cependant pas à autoriser une sélection automatique.
Les listes de candidats restent identiques. Le contraste nominal `bank` est
encore plus strict : même prédicat ERG et même signature `ARG1` malgré les sens
financier et géographique attendus.

ERG étend parfois le charspan lexical jusqu'à la ponctuation finale. La POC
conserve donc séparément le span source `bank` et le span réellement rendu par
l'EP, sans réécrire l'observation.

## Limites

SemLink 2 cible VerbNet 3.3 et Unified PropBank, tandis que les corpus NLTK
installés sont VerbNet 2.1 et PropBank 1.0. Les extrémités non résolues restent
présentes avec leur provenance. Les liens ne sont ni supprimés ni convertis en
équivalences.

Une intégration de production doit ajouter un composant explicite de
désambiguïsation contextuelle et de labellisation des rôles/frames. Sa sortie
devra rester une nouvelle analyse attribuée, conserver les alternatives et ne
jamais confondre un lookup ou un mapping avec une décision cognitive.
