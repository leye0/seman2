# Verdict RUN-02

`GO_COORDINATED_DURABLE_AND_COGNITIVE_RECONSTRUCTION` : la copie runtime
contient les 72 artefacts et événements, les sauvegardes agent/smem/epmem sont
présentes et attribuées, et un nouveau noyau Soar reproduit exactement les trois
décisions après reconstruction de la WM.

Un nouveau runtime cognitif restaure aussi l'arène, les activations, le
scheduler, le Control State et le curseur à mi-source. Après le second record,
son snapshot de 104 artefacts est identique par SHA-256 à celui d'une exécution
ininterrompue. Une corruption réelle de l'enveloppe et une permutation des
records sont toutes deux refusées.

Ce verdict qualifie explicitement la reprise comme reconstruction coordonnée;
il ne revendique pas un snapshot natif intégral de la working memory Soar.
