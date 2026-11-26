# Second-pass semantic review — selected rank-one corrections required

This is a **negative source/graph audit**, not a certificate of correctness.
Each entry identifies an observed wrong selected relation or lexical reading
and its grammatical correction. All are bound to original frozen rank-one
tree and graph SHA-256s in `confirmed_selected_defects.json`.

## Additional Novel-700 defects

| Case | Actual selected problem | Required interpretation |
| --- | --- | --- |
| N602 | RECIPIENT(expressed,answer) from in my answer mislabels a manner/location PP as the recipient of expression | Bind in my answer as medium/context of expressing, not a recipient |
| N609 | MODIFIER(me,during) attaches during this journey to me rather than came across event | Attach temporal during this journey to the came event |
| N616 | MODIFIER(Matlock,comma) targets literal punctuation instead of the following relative | Attach which was our next place of rest to Matlock with its copular predicate |
| N617 | loved in all it loved is typed ADJ rather than the finite verb loved | Build the relative modifying all with overt subject it and verbal loved |
| N622 | The root has no selected THEME/OBJECT relation from conceive to the horrors | Conceive governs the horrors, with as-clause subordinate and its own agents |
| N628 | Fronted Of Silver is reduced to TOPIC(heard,Of) with no Silver referent; no more object treated as AFFECTED | Connect Silver as topic of hearing and preserve negative quantifier no more |
| N632 | with a pistol in either hand only links TOPIC(addressed,with) and omits instrument/pistol | Attach instrumental with pistol and locative in either hand to addressed |
| N634 | Complex There was some sense in this generates only TOPIC(seemed,as) and TOPIC(seemed,Well) | Represent existential was some sense and epistemic as it seemed to me separately |
| N640 | Dick was gone but a little while yields CONJUNCT(gone,little) and while as a subordinating conjunction | Treat a little while as duration and the following Israel spoke as distinct coordinated clause |
| N642 | AGENT(cry,wrench) incorrectly makes a wrench the experiencer of crying | In made me cry out, me is controller/agent of cry; wrench is the causative instrument |
| N645 | MANNER(made,for) wrongly treats for shore as manner | for shore is destination/goal of made, and oars could take us expresses the comparative ability |
| N650 | not in No sir not I has no negative-scope relation; AGENT(agreed,all) obscures we | Preserve negative minor response and we all as the subject of agreed |
| N657 | go in see the phantoms ... go by me is typed ADJ, not bare verbal predicate | see selects an object-control/bare-infinitive motion predicate go |
| N658 | made the most of them has no selected AGENT/CONJUNCT link to petted them | Both petted and made share subject she, while as I may say is a parenthesis |
| N664 | in in in intervals is typed ADJ, producing APPOSITION(me,intervals) | Intervals when left alone is a locative-temporal adjunct, not apposition of me |
| N667 | The second comparative something less genteel is not represented as an ATTRIBUTE of his manner | Retain two parallel degree modifiers of his manner with than of yore as standard |
| N668 | word in parting word is selected as V and AFFECTED(send,parting) | Parting word is a noun phrase object of send; by me and to her lover are distinct adjuncts |
| N670 | RECIPIENT(had,knee) mislabels on her knee; which would have lasted attaches to basket | Knee is location for basket and relative which modifies basket of refreshments |
| N671 | not in could not be here has no negative polarity relation | Negate the copular/modal ability clause and attach without-regrets PP appropriately |
| N677 | ATTRIBUTE(write,uncommonly) incorrectly makes degree adverb the attribute of writing | uncommonly modifies fast, and fast is manner of write |
| N683 | LOCATION(were,always) mislabels a frequency adverb as location | always is frequency/time of the state were on most intimate terms |
| N684 | justify the hopes has no selected direct-object relation for hopes | The relative that could justify the hopes has subject gap Nothing and an overt object hopes |
| N686 | never in should never have said is left disconnected from said | Scope never over the perfect modal reported clause |
| N689 | AFFECTED(joined,drawing-room) treats the room as object instead of party | They joined the party at a proper hour in Lady Catherine's drawing-room |
| N693 | neither ... nor and coloured semicolon leave negative correlative scope disconnected | Neither that nor anything else is subject of awakened; encode its negative scope and distinct first clause |
| N694 | AGENT(was,as) treats the comparative/linking marker as subject of was his custom | Treat as was his custom as a parenthetical comparative statement of retired |
| N695 | Second were familiar is given AGENT(were,horses), ignoring neither carriage nor livery as its subject | Horses were post is one clause; carriage/livery coordinated subject of second were familiar |
| N698 | not is unlinked in had not been of age; had is selected V instead of perfect auxiliary | Past-perfect negation scopes over been of age and distinct temporal when-clause |
| N699 | exercise is selected V and given is N inside exercise had given to her complexion | exercise is noun subject, had auxiliary, given past participle governing brilliancy/result |

## Additional Novel-800 defects

| Case | Actual selected problem | Required interpretation |
| --- | --- | --- |
| N709 | Margaret is only TOPIC(can,Margaret) and make lacks its modal-agent role links | Margaret is vocative and I is agent of make under modal can |
| N711 | The second lost event has TOPIC(lost,glory) instead of coordination of utility and glory in the first clause | Utility and glory are parallel hope complements; the second I have lost my friend is independent |
| N714 | thus in Continuing thus is typed N rather than an adverb, missing manner of continuing | Thus is an adverbial manner modifier of Continuing |
| N715 | inasmuch is typed N and becomes AGENT(supposed,inasmuch) | inasmuch as introduces a causal subordinate whose subject is it, not a noun |
| N716 | from a strange ... situation is only MODIFIER(me,from), incorrectly attaching rescue source to patient | Attach source/location from situation to rescued event; restored to life has a result/goal |
| N717 | The graph lacks COMPLEMENT(promised,watch) and ties if condition to promised instead of watch/give | Promised governs watching and giving; if any new object should appear conditions those actions |
| N719 | The coordinate nominal father, brothers, Elizabeth attaches CONJUNCT(how,brothers), not a list object of left | How modifies left, with father/brothers/Elizabeth coordinated objects of left |
| N723 | AGENT(led,I) and missing passive patient/forced relation treat I as active causer of led | I is passive patient of was led and forced, governing coordinated infinitives examine and spend |
| N724 | nets were cast has were selected as V and AGENT(cast,where) | were cast is passive with nets as patient, independent of where he had disappeared |
| N727 | Ready in quoted Ready! is selected N rather than an adjectival state | Represent adjectival readiness minor speech act with overt cried reporter |
| N728 | That in That fixes it! is selected DET as a stand-alone subject | The demonstrative is a pronominal subject of fixes, not a determiner without a noun |
| N729 | We ran on deck has only AGENT(ran,We); on deck is disconnected | Attach on deck as location/goal of ran |
| N733 | different from any of the others only gives ATTRIBUTE(was,different) with no comparison standard | The standard from any of the others must attach to different |
| N734 | Prophetic in quoted Prophetic! is selected PROPER-NOUN | Prophetic is adjective elliptical predication reported by said the doctor |
| N736 | may in and now may I go is a modal node with no incident semantic edge | Modal permission/interrogative scope of go |
| N738 | Who's the best shot? reported clause has no copular subject or attribute relation for best shot | Who is subject or predicand of is, best shot its complement, and asked governs the question |
| N741 | we had shoved off and given way selects had as V and given as ADJ with ATTRIBUTE(had,shoved) | Past-perfect auxiliary had scopes over coordinated shove off and give way events |
| N742 | In that's your sort is it he added returning, added has no AGENT he despite explicit reporter | he is agent of added and returning pipe is its participial supplement |
| N743 | my good man selects man as V and AGENT(man,Benbow) | my good man is vocative, not a verb with Benbow as subject |
| N744 | dipping her bowsprit is a V-ING in selected tree but has no semantic attachment to rolled | Attach dipping as participial dependent event sharing ship as subject |
| N745 | There was no sound but that of ... has no existential/polarity relation for no sound | There existential introduces absent sound; but that denotes exception and following gerund belongs to breakers |
| N746 | ship's counter includes possessive ’s typed COPULA; relative boat which we brought has wrong possessor | Preserve ship genitive and attach boat-relative, with dropped as Redruth's shared-subject verb |
| N747 | asking in he was asking is selected N, so a thing ... he was asking becomes copular noun attribute | asking is present participle of ask and defines what old buccaneer was asking |
| N748 | he did is treated as a coordinated full event of owed rather than emphatic auxiliary reprise | he did is elliptical auxiliary reprise of owed me money; no new lexical action |
| N750 | was abroad in ends with in selected N, giving ATTRIBUTE(was,in) | in is a stranded source preposition with the copular abroad clause, not an attribute noun |
| N751 | Very! Very! has zero semantic graph edges and only two adjective nodes | Represent the overt repeated degree/exclamative speech act, not two unlinked attributes |
| N753 | was greatly altered has only THEME(was,She) and no link to the altered participle | altered is passive/resultative predicate with She its patient and greatly its modifier |
| N764 | and looked frightened has no selected coordination event/attribute in the semantic graph | My aunt is common subject of accelerated and looked frightened in the found that content |
| N765 | AGENT(chatter,making) makes the causative verb the actor of teeth chatter | teeth is actual subject of chatter; making expresses causation by Mr Dick |
| N766 | on being sent for selects being as N instead of passive nonfinite auxiliary | being sent for is a nonfinite passive of sent governing source on-PP |
| N767 | but made no sign has no selected CONJUNCT link from looked or AGENT made | He is agent of both looked and made, coordinated by but |
| N768 | MANNER(gave,away) incorrectly attaches away from she went away to gave | away modifies went, and that she went away is the result clause of such delight |
| N771 | CONJUNCT(one,table) coordinates a hand with the table, not one hand with the other | One of his hands and the other are coordinated absolutive/participial descriptions; table locative |
| N773 | had in I had put my chair away is selected lexical V, not finite perfect auxiliary | had auxiliary scopes over put, with I subject, before was going out |
| N776 | Lady Catherine seemed pleased has only AGENT(seemed,Catherine), omitting pleased predicate | pleased is predicative complement of seemed and Catherine experiencer |
| N779 | They were hopeless of remedy lacks any semantic relation involving remedy | Attach of remedy as argument/content of hopeless |
| N781 | Mrs. Bennet's eyes sparkled has only AGENT(sparkled,eyes) and no Bennet possession | Mrs Bennet is possessor of eyes, which are subject of sparkled |
| N783 | to look at a picture is only MODIFIER(her,look) in called her to look | her is object of called and controlled subject of look; picture object of look |
| N784 | Darcy had walked away treats had as lexical V and ATTRIBUTE(had,walked) | had is past perfect auxiliary of walked, with away/directional to-part PP |
| N785 | POSSESSOR(praise,sister) misattaches of his sister's proficiency | Sister is possessor of proficiency; proficiency is content of affectionate praise |
| N786 | RECIPIENT(thanked,goodness) treats goodness as recipient of thanked | him is recipient/addressee of thanked; for his goodness gives reason |
| N787 | CONJUNCT(interest,nothing) conjoins an infinitival noun with negative proform, and nothing is not negated | much to interest and nothing to justify inquiry are parallel objects and negative existential contrast |
| N789 | or is selected N in or rather taller and APPOSITION(height,or) | or rather taller is discourse correction of height comparison, not appositional noun |
| N790 | RECIPIENT(thrown,open) treats open as noun object of was thrown open | open is resultative predicate of door thrown, not recipient |
| N794 | AGENT(called,by) makes the passive by-preposition the actor instead of the arrival | the arrival of Saturday is causal agent of passive called, not lexical by |
| N799 | had in Mr Bingley had been is selected V modifying Bingley rather than perfect auxiliary | had auxiliary scopes over copula been and its predicative friend complement |
