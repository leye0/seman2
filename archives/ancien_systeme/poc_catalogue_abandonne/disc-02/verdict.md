# Verdict DISC-02

**GO — frontière RST attribuée, intégrée et causalement vérifiée.**

Les six sorties réelles traversent une Artifact Arena en 19 artefacts : six
sources, six observations, six analyses attribuées et une frontière de capacité
qui dépend causalement de toutes les analyses. Le texte source et les 27 EDUs
sont vérifiés par offsets exacts. Une sortie altérée est rejetée.

Le contrat observé contient segmentation, spans, relations, nuclearité et arbre
binaire imbriqué. Il ne contient dans ces résultats ni scores, ni signaux
explicites, ni liens secondaires eRST, ni graphe non arborescent, ni
attachements croisés, ni participants/tours structurés.

Le modèle peut avoir été entraîné sur des ressources GUM/eRST ; son contrat de
sortie observé demeure néanmoins un arbre RST binaire. Les propriétés absentes
ne sont ni reconstruites ni supposées par l'adaptateur. Cela qualifie la sortie
observée, pas toutes les capacités théoriques du corpus ou du modèle.
