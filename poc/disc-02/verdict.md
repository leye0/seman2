# Verdict DISC-02

**GO — frontière de capacité documentée.**

La sortie contient segmentation, spans, relations, nuclearité et arbre binaire
imbriqué. Elle ne contient dans ces résultats ni signaux explicites, ni liens
secondaires eRST, ni graphe non arborescent, ni attachements croisés, ni
participants/tours, ni scores.

Le modèle peut avoir été entraîné sur des ressources GUM/eRST ; son contrat de
sortie observé demeure néanmoins un arbre RST binaire. Les propriétés absentes
ne doivent pas être reconstruites ou supposées par l'adaptateur.
