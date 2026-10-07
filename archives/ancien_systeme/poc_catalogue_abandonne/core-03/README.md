# CORE-03 — Ingestion développementale réelle et reprise équivalente

La POC exécute trois segments bornés sur le roman réel :

1. premier record puis checkpoint;
2. restauration et traitement du second record;
3. exécution continue des deux mêmes records.

Elle compare ensuite les empreintes du nouveau cœur développemental et de
l'Artifact Arena. Les analyses MRS doivent toutes être adaptées une seule fois,
les candidats restent hypothétiques et aucun système high level ne relit la
source brute.

La charge est plafonnée à deux records, une unité par observation et quatre
workers. Le modèle RST lourd n'est pas lancé.
