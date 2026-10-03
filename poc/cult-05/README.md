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

```bash
./poc/cult-05/run.sh
```
