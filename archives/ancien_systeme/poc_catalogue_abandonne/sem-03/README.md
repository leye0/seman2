# SEM-03 — Transformations de forme par WFST

Compile sept relations de forme pondérées avec Pynini/OpenFst, conserve leur
type et leur règle d'origine, sérialise les FST et compose `io → i/o` avec
`i/o → input/output`. Chaque forme traverse désormais le vrai contrat cognitif
`Source → Observation → wfst-form-analysis`; les artefacts produits portent
leurs parents, ancres, spans et empreintes de source.

```bash
./poc/sem-03/run.sh
```

Le runner relit le FST sérialisé, vérifie sa table de symboles OpenFst et teste
un distracteur sans chemin. Un chemin est une relation formelle candidate,
jamais une correction ni une identité sémantique.
