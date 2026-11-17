# Final-pass specific semantic deficits in source-selected trees

These failures were identified in the **existing selected** tree/graph outputs; they are *not corrected* by this diagnostic. Their original SHA-256 digests are frozen in the defect ledger. No review is marked verified by this file.

| Case | Selected semantic problem | Required relation |
| --- | --- | --- |
| N604 | AGENT(troubled,speech) treats an informational speech as a volitional agent and AFFECTED(troubled,me) only as physical affectedness | The speech is a STIMULUS/CAUSE of distress; me is EXPERIENCER of being troubled, not agent and physical patient |
| N606 | AGENT(was,letter) attributes agency to letter in My letter was calm and affectionate | The copular subject letter is THEME/PREDICAND and calm/affectionate are two predicative attributes |
| N614 | MANNER(continued,still) classifies the persistence adverb still as manner; graph has ADJUNCT(enveloped,in) but never attaches the actual darkness nominal object | Still is ASPECTUAL/TEMPORAL persistence, and in an impenetrable darkness contributes the actual locative/state modifier of enveloped |
| N651 | The perfect auxiliary has in The boy has got the baby is absent from all semantic relations | The HAVE auxiliary expresses perfect aspect of got; full source quote and exclamatory illocution need correctly scoped representation |
| N656 | Hands in We shook hands heartily has semantic node type EVENT rather than a concrete body-part/object | Hands is the hand-object of shake (or reciprocal handshaking event participants), not itself typed as an independent event |
| N676 | MANNER(was,directly) treats directly in She was gone directly as manner of the copula | Directly is a temporal immediately/soon modifier of the departure/state gone, not manner |
| N754 | He made a short pause has no semantic relation for short despite the overt attributive modifier | Short restricts duration of the pause nominal / event and must be attached |
| N761 | The perfect HAVE in I have forgot her name is absent from the selected semantic graph | Have is the perfect auxiliary of forgot; the preceding A little woman is a separate discourse fragment or topic and must not silently blend with tense/aspect |
