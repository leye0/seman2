# Verdict GRAPH-03

**GO — ambiguïté conservée sans `argmax` destructif ni explosion combinatoire.**

Chaque candidat garde producteur, formalisme, contraintes, score natif éventuel,
payload et support GRAPH-02. Les conflits n'existent qu'à l'intérieur des
groupes exclusifs. Les actes DiAML multidimensionnels, les relations SDRT
croisées et les analyses ERG/Dynamic Syntax restent compatibles mais distincts.
Le produit cartésien potentiel est seulement compté : aucun de ses nœuds n'est
matérialisé et aucune sélection n'est inventée.

Tous les groupes viennent désormais de sorties mesurées, y compris l'ambiguïté
ISU de DLG-07. NetworkX et rustworkx concordent sur la topologie factorisée.

La provenance est vérifiée au niveau de la tranche source : sélecteur, artefact
et empreintes des payloads doivent correspondre à tous les candidats du groupe.
