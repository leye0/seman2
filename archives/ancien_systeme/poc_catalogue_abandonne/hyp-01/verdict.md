# Verdict HYP-01

**GO — observation, hypothèses, évidence et sélection ont des identités et des temporalités séparées.**

La sélection historique continue de résoudre H1 version 1 et son snapshot
d'origine après l'ajout de H1 version 2. Les empreintes de tous les objets de
`t1` restent identiques, la source `io` se reconstruit et les tables passent un
aller-retour Parquet/DuckDB.

Le runtime reproduit cet invariant dans neuf artefacts causaux. La révision est
un enfant append-only de H1-v1; l'événement historique conserve son empreinte
et continue de pointer vers H1-v1 et le snapshot original.
