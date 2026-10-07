# CULT-05 — Familles anonymes sur échanges humoristiques réels

Le POC sélectionne 2 400 posts réels du snapshot Reddit Arctic de mai 2018 et
rattache leurs commentaires et votes observés. Les familles sont apprises sur
des traits lexicaux hachés et structurels extraits automatiquement. Le nombre de
familles est choisi par silhouette, sans utiliser subreddit, flair, outcome ou
liste humaine de types d'humour comme entrée du clustering.

Chaque famille fournit termes distinctifs, propriétés structurelles, contextes,
réactions, exceptions et exemples auditables avec IDs et positions sources. Un
cinquième des posts, réservé par hash avant l'apprentissage, teste l'affectation
de surfaces entièrement absentes de l'entraînement.

La politique IND-05 est ensuite appliquée aux familles : leur gain prédictif
d'outcome réservé est positif mais inférieur à 1 %, les votes/commentaires sont
un proxy bruité et aucune stabilité temporelle n'est encore calculée. Elles
restent donc des candidats anonymes non promus. Les états Switchboard CULT-01
ne sont pas fusionnés avec eux, faute d'alignement appris entre corpus, espaces
de traits et unités d'observation.

```bash
./poc/cult-05/run.sh
```
