"""Persistent list of unfixed sentences. Add to it when scanning finds
a failure; remove when the sentence parses. Never rescan passing ones."""

# Indices into extract_sentences(..., limit=500) that currently FAIL.
# Format: (index, full_sentence_text)
UNFIXED = [
    # (7,   "Mom worked during the day, Dad sometimes worked from home, Eli was learning to read longer sentences, and somebody always needed the bathroom when somebody else was late."),
    # (63,  "Maya could describe the red door, but she realized that visitors would also need the street, the intersection, and perhaps a number."),
    # (88,  "Maya was tempted to say their plan had been unnecessary, but Jonah pointed out that surprises sometimes improved the plan."),
    # (97,  "They made a short list of things to do the night before."),
    # (121, "Beneath them she wrote: What changes when you do the same job in a hurry rather than carefully?"),
    # (141, "The missing lunch had been funny for everyone else, but she had been frightened of not having food when she needed it."),
    # (171, "One said, \"I know what happened.\" The other said, \"How do you know?\" Maya let both characters ask questions until the disagreement became more specific."),
    # (228, "He explained that old newspapers could contain errors too."),
    # (255, "Information has a source; a useful reader asks who made it, when, why, and how that person could know."),
    # (267, "Maya argued that Grandma should have the largest slice because she had baked it."),
    # (272, "She first divided a circle into four pieces and realized that four equal quarters could not give six people one piece each."),
    # (327, "Some afternoons were warm enough for short sleeves, and some mornings made her reach for a jacket."),
    # (328, "An app could display a temperature, but she still had to understand what the number meant."),
    # (410, "In class, the children practiced asking open questions, waiting for answers, and taking notes."),
    # (421, "Listening includes attention, patience, and respect for what another person chooses not to say."),
    # (424, "She learned that trust and permission mattered too."),
    # (452, "Maya began to see that a resource could be scarce because of time, location, or access, not merely money."),
    # (469, "Her own question was written beneath the exercise: What can you do when there are several good answers and not enough time?"),
]
