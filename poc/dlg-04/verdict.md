# Verdict DLG-04

**GO — adaptateur DiAML sans perte, strictement limité à l'import.**

- Formalisme ISO 24617-2/DiAML disponible : **oui**.
- Annotations DialogBank de référence disponibles : **oui**.
- Analyseur/classifieur automatique fourni par DialogBank : **non**.

Les trois documents couvrent plusieurs dimensions, annotations simultanées sur
un même segment, dépendances fonctionnelles/de feedback, liens rhétoriques,
participants et qualificateurs (`certainty`, `sentiment`). Chaque cible est
résolue et la représentation XML générique se reconstruit avec une signature
structurelle identique, y compris après sérialisation et nouveau parsing. Les
références de participants, segments, tokens, dépendances et liens rhétoriques
sont toutes résolues. Cela garantit la conservation des informations XML,
pas l'identité octet pour octet de la mise en forme ou des préfixes de namespace.
