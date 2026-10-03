# Verdict RUN-04

`GO_SOAR_OPERATOR_STATE_TRANSFORMATIONS` : trois ensembles de transformations
issues du vrai flow question-réponse sont proposés comme opérateurs Soar. Les
préférences sélectionnent `attach-answer-candidate`; 18 artefacts nouveaux
portent le runtime à 165 artefacts/événements sur trois époques. Chaque état
appliqué conserve les sources question et réponse dans son ascendance, garde le
QUD ouvert et n'affirme pas la vérité de la réponse. Les décisions opérateur
sont équivalentes après reconstruction de leurs checkpoints indépendants.
