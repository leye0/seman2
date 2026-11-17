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
