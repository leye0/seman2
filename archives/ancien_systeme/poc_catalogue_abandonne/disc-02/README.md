# DISC-02 — Nature exacte du formalisme fourni

Ingère les six sorties IsaNLP réellement calculées dans DISC-01 dans la chaîne
`Source → Observation → attributed-rst-analysis → rst-capability-boundary`.
L'adaptateur conserve le texte, les arbres natifs, EDUs, spans, relations,
nuclearités, modèle, révision et empreinte du résultat externe. L'auditeur de
niveau supérieur consomme ces artefacts — jamais les fixtures directement — et
classe chaque propriété d'après les champs réellement sérialisés, pas d'après
le nom `gumrrg`.

```bash
./poc/disc-02/run.sh
```

Le modèle lourd n'est pas rechargé : le POC vérifie les empreintes des
fixtures, métadonnées et résultats déjà produits par DISC-01. Il rejette aussi
une copie délibérément altérée et confirme que l'entrée vide adversariale avait
été refusée. Pour recalculer l'inférence native elle-même, utiliser le runner
borné de DISC-01 séparément.
