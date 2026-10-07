voici toutes les modifications que je ferais maintenant dans Cogent/TRIPS, d’après le code actuel, classées par priorité. Plusieurs sont des gains évidents, et quelques-unes doivent être derrière un mode fast avec fallback pour ne pas sacrifier la couverture.
1. Désactiver totalement la génération Graphviz des LF. Dans src/Systems/cogent/params.lisp, remplacer :
   (setq im::*show-lf-graphs* t)
   
   par :
   (setq im::*show-lf-graphs* nil)
   
   C’est un gain sans perte pour Seman2. Actuellement send-lf-graph appelle convert-terms-to-dot, donc construit une énorme string DOT pour rien.
2. Désactiver le pretty printing global.
   (setq *print-pretty* nil)
   
   au lieu de :
   (setq *print-pretty* t)
   
   Pour du batch, on veut des sorties compactes. Aucune perte sémantique.
3. Couper le tracing du Dialogue Agent. Actuellement :
   (dagent::trace-on 1)
   
   Remplacer par :
   (dagent::trace-off)
   
   Le niveau 1 trace les appels et sorties du matching. Pour des millions de phrases, c’est du bruit et de l’I/O inutile.
4. Laisser les loggers désactivés. Ils le sont déjà :
   (setq logging::*logging-enabled* nil)
   (setq logging2::*logging-enabled* nil)
   
   Ajouter un test de démarrage qui vérifie qu’aucun profil Seman2 ne les rallume.
5. Chercher un seul parse si on n’en retourne qu’un. Actuellement Cogent fait :
   (setf (parser::number-parses-to-find parser::*chart*) 2)
   (setf (parser::number-parses-desired parser::*chart*) 1)
   
   Pour le profil batch Seman2 :
   (setf (parser::number-parses-to-find parser::*chart*) 1)
   (setf (parser::number-parses-desired parser::*chart*) 1)
   
   C’est une modification importante : actuellement il continue exprès jusqu’au deuxième spanning parse avant de s’arrêter.
6. Forcer explicitement l’arrêt dès qu’une solution complète est trouvée.
   (setf (parser::stopwhensolutionsfound parser::*chart*) t)
   
   C’est déjà la valeur par défaut dans TRIPS, mais je l’inscrirais explicitement dans notre profil pour éviter toute régression. Le commentaire du code TRIPS dit carrément qu’ils ne recommandent pas de le désactiver.
7. Activer le beam pruning. C’est probablement le gros bouton actuellement laissé sur OFF :
   (parser::*beam-pruning-on* t)
   
   au lieu de :
   (parser::*beam-pruning-on* nil)
   
   Le code indique que ce mécanisme garde au maximum BEAM-WIDTH items entre deux positions. Cogent configure déjà :
   (parser::*beam-width* 20)
   
   mais n’utilise pas le beam.
8. Garder d’abord beam-width = 20. Ne commence pas par le massacrer à 5. Le premier benchmark doit être :
   (parser::*beam-width* 20)
   
   Ensuite tester 15, 10 seulement si la qualité reste stable.
9. Pruner plus souvent. Actuellement :
   (parser::*pruning-frequency* 500)
   
   Je commencerais avec :
   (parser::*pruning-frequency* 100)
   
   une fois le beam activé. Le compromis est davantage de travail de pruning, mais beaucoup moins de croissance incontrôlée de l’agenda. À benchmarker à 100, 200, 500.
10. Passer le semantic matching en strict lors du premier passage. Actuellement :
    (setf (parser::flexible-semantic-matching parser::*chart*) t)
    
    signifie explicitement : autoriser l’unification malgré des mismatches sémantiques. Ça conserve des branches supplémentaires. Pour Seman2 je ferais :
    (setf (parser::flexible-semantic-matching parser::*chart*) nil)
    
    mais avec fallback :
    strict parse
        ↓
    succès → terminé
        ↓ échec
    flexible semantic parse
    
    Ça donne le meilleur des deux mondes.
11. Limiter WordFinder aux mots inconnus du lexique TRIPS. Cogent a actuellement :
    (setq lxm::*use-wordfinder* t)
    
    mais *unknown-words-only* est disponible précisément pour ça. Ajouter :
    (setq lxm::*unknown-words-only* t)
    
    Le commentaire du code dit explicitement :
    si T, chercher les senses WordFinder seulement si le mot n’est pas défini dans TRIPS.
    
    Pour un corpus anglais normal, ça peut éliminer énormément de travail WordNet inutile.
12. Tester use-tagged-senses-only = t dans le profil rapide. Actuellement :
    (setq lxm::*use-tagged-senses-only* nil)
    
    Avec :
    (setq lxm::*use-tagged-senses-only* t)
    
    lorsque des tags de sens existent, LXM ne renvoie que ces senses au lieu de maintenir plus d’ambiguïtés lexicales. C’est potentiellement un gros gain, mais c’est une optimisation avec risque de rappel : fallback conseillé.
13. Garder les filtres POS et sense activés. Ils le sont déjà :
    (parser::*use-tags-as-filter* t)
    (parser::*use-senses-as-filter* t)
    
    Ne surtout pas les désactiver pour “simplifier”. Ils servent justement à réduire l’espace du parser.
14. Abandonner le parsing du paragraphe comme une seule unité. C’est probablement le changement structurel le plus important :
    MAUVAIS:
    paragraph → parse-text → COMPOUND-COMMUNICATION-ACT géant
    
    remplacer par :
    sentence 1 → TRIPS
    sentence 2 → TRIPS
    sentence 3 → TRIPS
    ...
    
    dans la même session persistante, afin de conserver le contexte.
15. Faire le sentence splitting avant le chart parser. TextTagger supporte explicitement :
    :split-sentences t
    
    Donc laisse TextTagger déterminer les frontières, puis parse chaque utterance séparément. Ne demande pas au parser symbolique d’inventer une couverture fragmentaire sur 300 caractères d’un coup.
16. Ne pas splitter par clauses par défaut. Utiliser :
    split-sentences = true
    split-clauses = false
    
    Sinon tu risques exactement ce que ton log montre : avalanche de petits SA_FRAGMENT.
17. TRIPS doit rester lancé en permanence. Aucun :
    start TRIPS
    parse phrase
    stop TRIPS
    
    Le bon modèle :
    start once
       ↓
    millions de requests
       ↓
    stop
    
    Ontologie, lexique, WordNetSQL et JVM/Lisp restent chauds.
18. Créer un Seman2IM minimal au lieu d’utiliser tout Cogent. C’est possiblement le plus gros gain après le sentence splitting. Le params.lisp utilise actuellement :
    (setq im::*current-dialog-manager* #'im::SequentialLFTransformIM)
    (setq im::*cps-control* t)
    
    puis lance les cogentRules, matching, extraction, CPS, etc.
    Mais Seman2 veut essentiellement :
    parser LF
    + syntax tree
    + spans
    + reference/coreference
    
    et pas le comportement applicatif Cogent.
    Le code contient déjà un indice très intéressant :
    ;; quick code to support reference resolution without full IM
    (defun p+ref ...)
    
    Donc créer :
    Seman2IM
    
    qui :
    - reçoit le LF ;
    - l’ajoute au im-record ;
    - résout les références ;
    - émet le résultat ;
    - ne lance aucun système d’extraction métier Cogent.
19. Désactiver CPS pour Seman2.
    Dans ce Seman2IM :
    (setq im::*cps-control* nil)
    
    Seman2 gère lui-même le flux d’entrées. Aucun besoin que Cogent orchestre le dialogue.
20. Ne pas exécuter cogentRules si Seman2 n’utilise pas leurs extractions. Actuellement :
    (setq im::*extraction-sequence* '((im::cogentRules)))
    
    Pour le mode Seman2 :
    (setq im::*extraction-sequence* nil)
    
    sous réserve que notre minimal IM collecte bien les LF directement. Pourquoi faire du rule matching sur toutes les LF si le niveau 3 Seman2 va travailler directement dessus ?
21. Désactiver les optional LF matches si le full IM reste actif. Actuellement :
    (setq im::*allow-optional-lfs* t)
    
    Ce mode fait du traitement supplémentaire dans MatchEngine. En Seman2 :
    (setq im::*allow-optional-lfs* nil)
    
    sauf si on démontre qu’on a besoin de cette flexibilité.
22. Si on conserve le MatchEngine, remettre les covers strictement disjoints. Le défaut du moteur est :
    *max-cover-with-strict-disjoint-extractions* t
    
    mais Cogent le force à :
    nil
    
    Je testerais :
    (setq im::*max-cover-with-strict-disjoint-extractions* t)
    
    pour réduire les combinaisons. Là encore, inutile si on bypass le MatchEngine.
23. Ne pas générer plusieurs représentations textuelles de la même LF. Notre adapter Seman2 doit recevoir une structure native, pas :
    Lisp LF
    + Graphviz LF
    + XML
    + RDF
    + pretty-print
    + log complet
    
    Une seule représentation canonique + provenance.
24. Conserver l’arbre syntaxique, mais éviter un second parcours coûteux si possible. Dans Trips-parser.lisp, après le parse, TRIPS fait :
    (get-parse :lf ...)
    
    puis, si l’arbre est demandé :
    (get-parse :syntax ...)
    
    Donc deux extractions à partir du chart. Pour Seman2, je créerais une fonction :
    get-seman2-analysis
    
    qui récupère le meilleur chart entry une fois et construit LF + arbre à partir du même résultat.
25. Ne demander que les features syntaxiques utiles. Actuellement :
    (setf parser::*include-parse-tree-in-messages* '(w::lex))
    
    C’est déjà plutôt raisonnable. Ne l’élargis surtout pas à 15 features. Pour DOP, W::LEX + structure devrait suffire au départ. Ajouter une feature seulement si l’algorithme en a besoin.
26. Réécrire convert-terms-to-dot si on veut quand même conserver Graphviz en debug. Il fait des :
    (setq res (append res ...))
    
    dans une boucle. C’est un pattern coûteux. Le remplacer par :
    with-output-to-string
    
    et format directement dans le stream, ou construire avec push + nreverse. Mais en batch, mieux : ne jamais appeler la fonction.
27. Supprimer les append répétés dans les hot paths de sérialisation. Même principe dans tout code exécuté par utterance :
    append-growing-list
    
    → remplacer par :
    push/nreverse
    
    ou vectors ajustables/streams.
28. Ajouter du memoization autour des lookups lexicaux réellement répétitifs. WordFinder a déjà plusieurs caches internes, mais notre couche peut aussi mémoriser par :
    lowercase word + POS + configuration
    
    les résultats LXM/WordNet fréquemment demandés. Un corpus répète énormément les mêmes mots.
29. Précharger les caches statiques au démarrage. Toute donnée immutable telle que voisinages LF/WordNet, mappings ontology→sense et tables lexicales doit être préparée une fois. WordFinder possède déjà des fonctions/cache structures pour certains de ces cas : on doit s’assurer qu’elles sont exploitées plutôt que recalculées durant le batch.
30. Mettre une limite de temps/complexité par phrase et fallback. Pour empêcher :
    phrase pathologique
    → 2 minutes
    
    il faut un budget :
    fast parse
    ≤ X chart entries / Y secondes
    
    si dépassement :
    fallback parse moins ambitieux
    
    et conserver le statut partial.
31. Utiliser deux profils explicites plutôt qu’un seul compromis bancal.
    Je créerais :
    seman2-fast
    seman2-deep
    
    fast :
    beam-pruning          T
    beam-width            20
    parses-to-find        1
    flexible-semantics    NIL
    unknown-words-only    T
    show-lf-graphs        NIL
    tracing               OFF
    
    deep :
    beam-pruning          NIL ou beam large
    parses-to-find        2+
    flexible-semantics    T
    wordfinder complet
    
    Le système fait fast, puis deep uniquement si nécessaire.
32. Batcher au niveau des processus, pas en donnant de gros paragraphes à un parser. Pour compiler un gros corpus, lancer plusieurs instances TRIPS indépendantes si elles sont thread/process safe au niveau système :
    worker 1 → documents A
    worker 2 → documents B
    worker 3 → documents C
    worker 4 → documents D
    
    Chaque worker garde son propre contexte à l’intérieur d’un document/conversation. Ne parallélise jamais les phrases d’une même conversation si le contexte est important.
33. Faire le cache des analyses au niveau Seman2. Hash :
    raw_text
    + parser build
    + parser profile
    + context identifier
    
    Si déjà analysé :
    return cache
    
    TRIPS ne doit jamais reparser gratuitement le même corpus.
34. Instrumenter avant toute micro-optimisation supplémentaire. Ajouter des compteurs par phrase :
    texttagger_ms
    lexicon_ms
    wordfinder_ms
    parser_ms
    chart_entries
    parses_found
    im_ms
    serialization_ms
    total_ms
    
    Sans ça, on risque de passer 4 heures à optimiser convert-terms-to-dot alors que 95 % est dans le chart parser.
Le bloc params.lisp minimal que je demanderais immédiatement à ton agent est donc :
;; ============================
;; Seman2 FAST parsing profile
;; ============================

;; Output / debug
(setq im::*show-lf-graphs* nil)
(setq *print-pretty* nil)
(dagent::trace-off)
(setq logging::*logging-enabled* nil)
(setq logging2::*logging-enabled* nil)

;; Parser search
(setf (parser::number-parses-to-find parser::*chart*) 1)
(setf (parser::number-parses-desired parser::*chart*) 1)
(setf (parser::stopwhensolutionsfound parser::*chart*) t)

(setq parser::*beam-pruning-on* t)
(setq parser::*beam-width* 20)
(setq parser::*pruning-frequency* 100)

;; Strict first-pass semantics
(setf (parser::flexible-semantic-matching parser::*chart*) nil)

;; Keep useful pruning filters
(setq parser::*use-tags-as-filter* t)
(setq parser::*use-senses-as-filter* t)

;; Lexicon / WordNet
(setq lxm::*use-wordfinder* t)
(setq lxm::*unknown-words-only* t)

;; IM — only if the full Cogent IM is temporarily retained
(setq im::*allow-optional-lfs* nil)
(setq im::*max-cover-with-strict-disjoint-extractions* t)

Et le vrai objectif après ça est de supprimer du chemin critique tout ce bloc :
full Cogent dialogue machinery
CPS
cogentRules
LF Graphviz
paragraph compound parsing
optional extraction matching

pour arriver à :
TextTagger
   ↓ sentence boundary
Parser
   ↓
best LF + syntax
   ↓
minimal reference resolution
   ↓
Seman2 adapter

C’est cette version que je considère comme TRIPS optimisé pour Seman2, plutôt que « Cogent utilisé tel quel ».