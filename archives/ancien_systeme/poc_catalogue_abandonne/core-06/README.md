# CORE-06 — Continuité d'identité et facettes contextuelles

La POC sépare l'identité candidate d'un individu de ses facettes situées. Elle
teste un cas positif de continuité, une ambiguïté entre homonymes et un conflit
de traits grammaticaux.

Le résolveur retourne toujours un beam incluant la possibilité d'une nouvelle
identité. Une fusion n'est appliquée qu'après sélection explicite et conserve
une facette distincte par contexte.
