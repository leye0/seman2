"""Integration tests: parse real English strings with the seed data."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import Parser
from seman_parser.chart import Chart
from seman_parser.engine import ParserResources
from seman_parser.grammar import load_grammar
from seman_parser.lexicon import load_lexicon
from seman_parser.segmentation import build_lattice

DATA = Path(__file__).resolve().parents[1] / "data"


def make_parser() -> Parser:
    return Parser.from_dir(DATA)



class CausalDashInciseAndUnicodeGenitiveTests(unittest.TestCase):
    """Source-offset preserving grammar tests for literary parentheticals."""

    @staticmethod
    def rule_ids(node):
        yield node.rule_id
        for child in node.children:
            yield from CausalDashInciseAndUnicodeGenitiveTests.rule_ids(child)

    def test_be_copular_valence_cannot_license_transitive_object_gap(self):
        lattice = make_parser().parse("were").lattice
        self.assertTrue(any(c.category == "COPULA" for c in lattice.candidates))
        for candidate in lattice.candidates:
            if candidate.category != "V":
                continue
            if candidate.lemma.casefold() not in {"be", "was", "is", "are"}:
                continue
            valence = candidate.features.as_dict().get("subcat")
            alternatives = valence if isinstance(valence, list) else [valence]
            self.assertNotIn("transitive", alternatives,
                             "BE's nominal attribute is not an object gap.")

    def test_possessive_determiner_is_not_a_suffix_clitic(self):
        parser = Parser(make_parser().resources, goal_category="NP")
        possessive = parser.parse("his eyes", diagnostic_k=32).result
        self.assertTrue(possessive.completed, possessive.stats)
        self.assertTrue(any(
            "np_poss" in set(self.rule_ids(tree))
            for tree in possessive.alternatives(limit=32)
        ), possessive.stats)
        for phrase in ("'s eyes", "’s eyes"):
            with self.subTest(phrase=phrase):
                result = parser.parse(phrase, diagnostic_k=32).result
                self.assertFalse(any(
                    "np_poss" in set(self.rule_ids(tree))
                    for tree in result.alternatives(limit=32)
                ), "An apostrophe-s clitic cannot independently head a possessor NP.")

    def test_dash_bounded_causal_for_requires_two_overt_dashes(self):
        parser = make_parser()
        positive = parser.parse(
            "Mary--for she was ready--left.", diagnostic_k=32,
        ).result
        self.assertTrue(positive.completed, positive.stats)
        self.assertTrue(any(
            "parenthetical_dash_causal_clause" in set(self.rule_ids(tree))
            for tree in positive.alternatives(limit=32)
        ), positive.stats)
        for sentence in (
            "Mary--because she was ready--left.",
            "Mary--for she was ready-left.",
            "Mary for she was ready left.",
        ):
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence, diagnostic_k=32).result
                self.assertFalse(any(
                    "parenthetical_dash_causal_clause" in set(self.rule_ids(tree))
                    for tree in result.alternatives(limit=32)
                ), sentence)

    def test_curly_apostrophe_genitive_keeps_overt_morpheme_span(self):
        parser = Parser(make_parser().resources, goal_category="NP")
        for phrase, mark in (("John's mother", "'s"), ("John’s mother", "’s")):
            with self.subTest(phrase=phrase):
                result = parser.parse(phrase, diagnostic_k=32).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(
                    {"np_poss_s", "np_genitive"} & set(self.rule_ids(result.best())),
                    "The apostrophe-s must be a genitive, not a zero relative.",
                )
                start = phrase.index(mark)
                lattice = parser.parse(phrase).lattice
                self.assertTrue(any(
                    c.span_start == start and c.span_end == start + len(mark)
                    and c.category == "POSS"
                    and c.features.as_dict().get("genitive_clitic") == "true"
                    for c in lattice.candidates
                ))




class ResidualLiteraryCoverageTests(unittest.TestCase):
    """Paired lexical and construction tests for three residual novel cases."""

    @staticmethod
    def rule_ids(node):
        yield node.rule_id
        for child in node.children:
            yield from ResidualLiteraryCoverageTests.rule_ids(child)

    def test_lexical_licenses_are_specific_and_preserve_regular_readings(self):
        p = make_parser()
        expected = (
            ("within", "PREP", None),
            ("rather", "ADV", "rather_infinitival_alternative"),
            ("than", "CONJ", "infinitival_comparison_marker"),
            ("for", "PREP", "supplementary_benefactive"),
        )
        for surface, category, feature in expected:
            with self.subTest(surface=surface):
                candidates = [
                    c for c in p.parse(surface).lattice.candidates
                    if c.surface.casefold() == surface and c.category == category
                ]
                self.assertTrue(candidates, (surface, category))
                if feature:
                    self.assertTrue(any(
                        c.features.as_dict().get(feature) == "true"
                        for c in candidates
                    ), (surface, feature))
        for other in ("and", "or", "but"):
            with self.subTest(other=other):
                self.assertFalse(any(
                    c.features.as_dict().get("infinitival_comparison_marker") == "true"
                    for c in p.parse(other).lattice.candidates
                ))

    def test_subject_control_rather_than_requires_explicit_comparison(self):
        p = make_parser()
        positive = p.parse("Mary tried rather to walk than run.").result
        self.assertTrue(positive.completed, positive.stats)
        rule = "vp_subject_control_rather_to_than"
        self.assertTrue(any(
            rule in set(self.rule_ids(root))
            for root in positive.alternatives(limit=8)
        ))
        unlicensed = p.parse("Mary tried rather to walk and run.").result
        self.assertFalse(any(
            rule in set(self.rule_ids(root))
            for root in unlicensed.alternatives(limit=8)
        ))

    def test_subject_raising_is_distinct_from_control(self):
        p = make_parser()
        cases = (
            ("He seemed to grow tired.", "vp_finite_raising_to_infinitive"),
            ("He seemed rather to grow weaker than regain his strength.",
             "vp_finite_raising_rather_to_than"),
        )
        for sentence, expected_rule in cases:
            with self.subTest(sentence=sentence):
                result = p.parse(sentence, diagnostic_k=128, beam=128).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(any(
                    expected_rule in set(self.rule_ids(root))
                    for root in result.alternatives(limit=128)
                ), expected_rule)

    def test_all_degree_as_rules_require_overt_lexical_degree(self):
        grammar = load_grammar(DATA / "grammar.jsonl")
        marked = [
            (rule.rule_id, symbol)
            for rule in grammar.rules
            for symbol in rule.rhs
            if symbol.category == "CONJ"
            and symbol.features.as_dict().get("degree") == "true"
        ]
        self.assertGreaterEqual(len(marked), 10)
        for rule_id, symbol in marked:
            with self.subTest(rule=rule_id):
                self.assertIn("degree", symbol.requires)

        pp = Parser(make_parser().resources, goal_category="PP")
        invalid = pp.parse("than most children", diagnostic_k=32).result
        for root in invalid.alternatives(limit=32):
            self.assertNotIn("pp_as_adj_np", set(self.rule_ids(root)))

    def test_degree_as_avoids_comparative_than_attachment(self):
        p = Parser(make_parser().resources, goal_category="PP")
        construction = "pp_as_adj"
        degree_as = p.parse("as happy", diagnostic_k=32).result
        self.assertTrue(degree_as.completed, degree_as.stats)
        self.assertTrue(any(
            construction in set(self.rule_ids(root))
            for root in degree_as.alternatives(limit=32)
        ))
        bare_than = p.parse("than happy", diagnostic_k=32).result
        self.assertFalse(any(
            construction in set(self.rule_ids(root))
            for root in bare_than.alternatives(limit=32)
        ), "Comparative than cannot be promoted to a degree-as PP.")

    def test_bare_conjunction_cannot_complete_a_nominal_head(self):
        grammar = load_grammar(DATA / "grammar.jsonl")
        self.assertFalse(any(
            rule.lhs.category == "NP"
            and tuple(symbol.category for symbol in rule.rhs) == ("N", "CONJ")
            for rule in grammar.rules
        ), "A noun followed by a subordinating conjunction is not an NP.")
        np_parser = Parser(make_parser().resources, goal_category="NP")
        malformed = np_parser.parse("water than").result
        self.assertFalse(malformed.completed, malformed.stats)
        coordinated = np_parser.parse("water and bread").result
        self.assertTrue(coordinated.completed, coordinated.stats)

    def test_negative_coordinator_licenses_modal_inversion_only(self):
        p = make_parser()
        construction = "clause_negative_coordinator_modal_inversion"
        for sentence in (
            "Nor could Mary leave.",
            "John waited, nor could Mary leave.",
            "Nor could I ask information from a single human being.",
        ):
            with self.subTest(sentence=sentence):
                result = p.parse(sentence, diagnostic_k=32).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(any(
                    construction in set(self.rule_ids(root))
                    for root in result.alternatives(limit=32)
                ), (sentence, result.stats))
        for sentence in (
            "And could Mary leave.",
            "But could Mary leave.",
        ):
            with self.subTest(unlicensed=sentence):
                result = p.parse(sentence, diagnostic_k=32).result
                self.assertFalse(any(
                    construction in set(self.rule_ids(root))
                    for root in result.alternatives(limit=32)
                ))

    def test_negative_coordinator_supports_auxiliary_and_copular_inversions(self):
        p = make_parser()
        examples = (
            ("Nor did Mary leave.",
             "clause_negative_coordinator_aux_inversion"),
            ("Nor was that wonderful.",
             "clause_negative_coordinator_copular_adj_inversion"),
            ("Nor was Mary a fool.",
             "clause_negative_coordinator_copular_nominal_inversion"),
        )
        for sentence, expected in examples:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence, diagnostic_k=32).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertTrue(any(
                    expected in set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=32)
                ), (sentence, parsed.stats))
                if sentence == "Nor did Mary leave.":
                    self.assertIn(
                        expected, set(self.rule_ids(parsed.best())),
                        "Overt nor inversion must outrank a spurious polar question.",
                    )
        restricted = (
            "And did Mary leave.",
            "But was that wonderful.",
            "And was Mary a fool.",
        )
        new_rules = {expected for _, expected in examples}
        for sentence in restricted:
            with self.subTest(unlicensed=sentence):
                parsed = p.parse(sentence, diagnostic_k=32).result
                self.assertFalse(any(
                    new_rules & set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=32)
                ))

    def test_original_negative_inversion_is_not_spurious_recognition(self):
        p = make_parser()
        sentence = (
            "I did not know the names of the towns that I was to pass through, "
            "nor could I ask information from a single human being."
        )
        parsed = p.parse(sentence, diagnostic_k=32).result
        self.assertTrue(parsed.completed, parsed.stats)
        self.assertIn(
            "clause_negative_coordinator_modal_inversion",
            set(self.rule_ids(parsed.best())),
        )

    def test_original_copular_nor_uses_licensed_inversion(self):
        p = make_parser()
        sentence = (
            "Nor was that wonderful, seeing how cavalier had been "
            "the captain's answer."
        )
        parsed = p.parse(sentence, diagnostic_k=32).result
        self.assertTrue(parsed.completed, parsed.stats)
        # This certifies the inversion, not the selected adjectival-vs-nominal
        # predicate or the following participial attachment. Audit the entire
        # selected tree in core CI before claiming syntactic quality.
        self.assertTrue(
            {
                "clause_negative_coordinator_copular_adj_inversion",
                "clause_negative_coordinator_copular_nominal_inversion",
            } & set(self.rule_ids(parsed.best())),
            parsed.stats,
        )

    def test_selected_object_control_and_perfect_in_original_literary_tree(self):
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        from scripts.diagnose_novel_parses import select_cases

        p = make_parser()
        # The Gutenberg case carries its own synthetic closing quotation
        # mark.  Keep the exact canonical quote-transfer provenance.
        cohort, _ = select_cases(500)
        case = cohort[359]
        prepared, _, result = parse_corpus_case(
            p, case, max_items=50_000, kbest_work_limit=500_000,
        )
        sentence = prepared.analysis_text
        self.assertIn(
            "The Turk allowed this intimacy to take place", sentence,
        )
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertIsNotNone(best)
        assert best is not None

        def selected_spans(node):
            yield (node.rule_id, sentence[node.start:node.end])
            for child in node.children:
                yield from selected_spans(child)

        spans = set(selected_spans(best))
        self.assertIn(
            ("vp_obj_control", "allowed this intimacy to take place"), spans,
            "The infinitive must be selected as the complement of allowed, "
            "not part of a second nominal object.",
        )
        self.assertIn(
            ("vp_perfect_trans", "had formed far other plans"), spans,
            "Finite HAVE must select the past participle and its object.",
        )

    def test_control_and_perfect_preference_preserves_contrasts(self):
        p = make_parser()
        examples = (
            ("Mary allowed John to leave.", "vp_obj_control"),
            ("Mary had formed a plan.", "vp_perfect_trans"),
            ("John gave Mary the box.", "vp_ditransitive"),
            ("Mary had a plan.", "vp_transitive"),
        )
        for sentence, expected in examples:
            with self.subTest(sentence=sentence):
                result = p.parse(sentence, diagnostic_k=32).result
                self.assertTrue(result.completed, result.stats)
                self.assertIn(
                    expected, set(self.rule_ids(result.best())),
                    (sentence, expected, result.stats),
                )

    def test_degree_before_indefinite_noun_has_real_article_and_head(self):
        p = make_parser()
        rule = "np_prenominal_degree_adjective_indefinite_noun"
        for sentence in (
            "Mary saw so arduous an undertaking.",
            "Mary saw too steep a hill.",
        ):
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence, diagnostic_k=32).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertTrue(any(
                    rule in set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=32)
                ))
        for sentence in (
            "Mary saw so arduous the undertaking.",
            "Mary saw much arduous an undertaking.",
        ):
            with self.subTest(unlicensed=sentence):
                parsed = p.parse(sentence).result
                self.assertFalse(any(
                    rule in set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=8)
                ))

    def test_perfect_reporting_predicate_selects_a_proposition(self):
        p = make_parser()
        for sentence, construction in (
            ("I have said the captain was weak.",
             "vp_perfect_clausal_zero_complement"),
            ("I have said that the captain was weak.",
             "vp_perfect_clausal_that_complement"),
        ):
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence, diagnostic_k=32).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertTrue(any(
                    construction in set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=32)
                ), construction)

    def test_postverbal_not_requires_overt_clausal_complement(self):
        p = make_parser()
        rule = "vp_finite_clausal_not_that"
        result = p.parse("I doubted not that I should succeed.",
                         diagnostic_k=32).result
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(any(
            rule in set(self.rule_ids(root))
            for root in result.alternatives(limit=32)
        ))
        negative = p.parse("I doubted not the book.").result
        self.assertFalse(any(
            rule in set(self.rule_ids(root))
            for root in negative.alternatives(limit=8)
        ))

    def test_coordinator_plus_indeed_is_clausal_not_nominal(self):
        p = make_parser()
        parsed = p.parse("And indeed he seemed tired.",
                         diagnostic_k=32).result
        self.assertTrue(parsed.completed, parsed.stats)
        self.assertTrue(any(
            "clause_initial_coordinator_discourse_adverb"
            in set(self.rule_ids(root))
            for root in parsed.alternatives(limit=32)
        ))
        self.assertFalse(any(
            "np_coord_adv" in set(self.rule_ids(root))
            for root in parsed.alternatives(limit=1)
        ), "The conjunction and discourse adverb must not become the subject.")

    def test_nominal_focus_particles_are_not_generic_discourse_adverbs(self):
        p = make_parser()
        for particle in ("even", "only", "just"):
            with self.subTest(particle=particle):
                self.assertTrue(any(
                    c.category == "ADV" and
                    c.features.as_dict().get("nominal_focus") == "true"
                    for c in p.parse(particle).lattice.candidates
                ))
        for particle in ("indeed", "nevertheless"):
            with self.subTest(unlicensed=particle):
                self.assertFalse(any(
                    c.category == "ADV" and
                    c.features.as_dict().get("nominal_focus") == "true"
                    for c in p.parse(particle).lattice.candidates
                ))
        nominal = p.parse("And even he could speak.", diagnostic_k=32).result
        self.assertTrue(nominal.completed, nominal.stats)
        self.assertTrue(any(
            "np_coord_adv" in set(self.rule_ids(root))
            for root in nominal.alternatives(limit=32)
        ))
        discourse = p.parse("And indeed he could speak.",
                            diagnostic_k=32).result
        self.assertTrue(discourse.completed, discourse.stats)
        self.assertFalse(any(
            "np_coord_adv" in set(self.rule_ids(root))
            for root in discourse.alternatives(limit=32)
        ))

    def test_with_absolute_keeps_predicate_inside_oblique(self):
        p = make_parser()
        # Audit the constituent itself instead of assuming that a short
        # matrix clause's top 32 k-best trees expose this low-ranked PP.
        oblique = Parser(p.resources, goal_category="PP")
        absolute = oblique.parse("with some brandy left",
                                 diagnostic_k=64).result
        self.assertTrue(absolute.completed, absolute.stats)
        self.assertTrue(any(
            "pp_absolute_with_np_adjp" in set(self.rule_ids(root))
            for root in absolute.alternatives(limit=64)
        ))
        typed = Parser(p.resources, goal_category="PP-ABSOLUTE")
        for phrase in ("with some brandy left", "with her eyes open"):
            self.assertTrue(typed.parse(phrase).result.completed, phrase)
        for phrase in ("with some brandy", "with her eyes"):
            self.assertFalse(typed.parse(phrase).result.completed, phrase)
        sentence = "Mary saw a bottle with some brandy left."
        matrix = p.parse(sentence).result
        self.assertTrue(matrix.completed, matrix.stats)

    def test_selected_with_absolute_modifies_the_bottle_not_the_finding(self):
        p = make_parser()
        sentence = (
            "Foraging about, I found a bottle with some brandy left, "
            "for Hands."
        )
        parsed = p.parse(sentence, diagnostic_k=64).result
        self.assertTrue(parsed.completed, parsed.stats)
        best = parsed.best()
        self.assertIsNotNone(best)
        assert best is not None

        def selected_spans(node):
            yield node.rule_id, sentence[node.start:node.end]
            for child in node.children:
                yield from selected_spans(child)

        spans = set(selected_spans(best))
        self.assertIn(
            ("np_det_head_with_absolute_modifier", "a bottle with some brandy left"),
            spans, "The with-absolute must be the nominal modifier.",
        )
        self.assertIn(
            ("pp_absolute_with_np_adjp", "with some brandy left"),
            spans, "Left is the secondary predicate of brandy, not a VP adverb.",
        )
        self.assertNotIn(
            ("vp_adv", "found a bottle with some brandy left"),
            spans, "The finding event cannot take 'left' as an adverb.",
        )

        ordinary = p.parse("Mary found a bottle with a label.",
                           diagnostic_k=32).result
        self.assertTrue(ordinary.completed, ordinary.stats)
        self.assertFalse(any(
            "np_det_head_with_absolute_modifier" in set(self.rule_ids(root))
            for root in ordinary.alternatives(limit=32)
        ), "An ordinary with-NP must not become a predicative absolute.")

    def test_selected_raising_outweighs_incidental_control_for_seem(self):
        p = make_parser()
        sentence = (
            "I have said the captain was weak, and indeed he seemed "
            "rather to grow weaker than regain his strength."
        )
        result = p.parse(sentence, diagnostic_k=64).result
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertIsNotNone(best)
        assert best is not None

        def selected_spans(node):
            yield node.rule_id, sentence[node.start:node.end]
            for child in node.children:
                yield from selected_spans(child)

        spans = set(selected_spans(best))
        complement = "seemed rather to grow weaker than regain his strength"
        self.assertIn(
            ("vp_finite_raising_rather_to_than", complement), spans,
            "The selected seem-construction is raising, not subject control.",
        )
        self.assertNotIn(
            ("vp_subject_control_rather_to_than", complement), spans,
        )

        control = p.parse("Mary tried rather to walk than run.",
                          diagnostic_k=32).result
        self.assertTrue(control.completed, control.stats)
        self.assertIn(
            "vp_subject_control_rather_to_than",
            set(self.rule_ids(control.best())),
            "Genuine subject-control should remain available and preferred.",
        )

    def test_productive_genitive_clitic_selects_possessed_nominal_head(self):
        parser = Parser(make_parser().resources, goal_category="NP")
        genitive_rules = {"np_poss_s", "np_genitive"}
        for phrase in (
            "Anderson's ball",
            "John's mother",
            "John’s mother",
            "the sailor's coat",
        ):
            with self.subTest(genitive=phrase):
                result = parser.parse(phrase, diagnostic_k=32).result
                self.assertTrue(result.completed, (phrase, result.stats))
                best = result.best()
                self.assertIsNotNone(best)
                assert best is not None
                selected_rules = set(self.rule_ids(best))
                if not genitive_rules.intersection(selected_rules):
                    lattice = parser.parse(phrase, diagnostic_k=32).lattice
                    candidates = [
                        (c.surface, c.span_start, c.span_end, c.category,
                         c.features.as_dict(), c.source)
                        for c in lattice.candidates
                    ]
                    alternatives = [
                        [rule for rule in self.rule_ids(root) if rule is not None]
                        for root in result.alternatives(limit=8)
                    ]
                    self.fail((
                        "A productive nominal possessor must attach to its "
                        "head noun rather than be an N compound.",
                        phrase, candidates,
                        [rule for rule in selected_rules if rule is not None],
                        alternatives,
                    ))

        for phrase in ("Andersons ball", "the sailor coat"):
            with self.subTest(non_genitive=phrase):
                result = parser.parse(phrase, diagnostic_k=32).result
                self.assertFalse(any(
                    genitive_rules.intersection(self.rule_ids(root))
                    for root in result.alternatives(limit=32)
                ), "Without an overt apostrophe-s, no genitive rule is licensed.")

    def test_comma_reporting_requires_lexical_clausal_valency(self):
        p = Parser(make_parser().resources, goal_category="VP")
        constructions = {"vp_colon_question", "vp_comma_clause"}
        for phrase in ("said, Mary had left", "said, John was ready"):
            with self.subTest(licensed=phrase):
                result = p.parse(phrase, diagnostic_k=32).result
                self.assertTrue(result.completed, (phrase, result.stats))
                self.assertTrue(any(
                    constructions.intersection(self.rule_ids(root))
                    for root in result.alternatives(limit=32)
                ), "Finite reporting verb has an attested clausal complement.")

        for phrase in (
            "sprinted, Mary had left",
            "ball, John was ready",
            "ball--for it was Job that shot him first",
        ):
            with self.subTest(unlicensed=phrase):
                result = p.parse(phrase, diagnostic_k=32).result
                self.assertFalse(any(
                    constructions.intersection(self.rule_ids(root))
                    for root in result.alternatives(limit=32)
                ), (
                    "An arbitrary finite verb must not report a comma clause.",
                    phrase,
                    [
                        (c.category, c.features.as_dict(), c.provenance)
                        for c in p.parse(phrase).lattice.candidates
                        if c.surface == phrase.split(",", 1)[0]
                    ],
                    [
                        sorted(set(self.rule_ids(root)) & constructions)
                        for root in result.alternatives(limit=16)
                    ],
                ))

    def test_reporting_discourse_coordination_is_matrix_scope(self):
        p = make_parser()
        source = (
            "I have said the captain was weak, and indeed he seemed "
            "rather to grow weaker than regain his strength."
        )
        result = p.parse(source, diagnostic_k=64).result
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertIsNotNone(best)
        assert best is not None

        def selected_spans(node):
            yield (node.rule_id, source[node.start:node.end])
            for child in node.children:
                yield from selected_spans(child)

        spans = set(selected_spans(best))
        self.assertIn(
            ("clause_comma", source.rstrip(".")), spans,
            "The overt discourse conjunct must attach to the reporting matrix.",
        )
        self.assertTrue(
            result.stats.get("matrix_discourse_tiebreak_applied"),
            "A score-tied lexical reporting/discourse ambiguity was resolved.",
        )
        self.assertIn(
            ("vp_perfect_clausal_zero_complement",
             "have said the captain was weak"), spans,
            "The reported proposition must end before the discourse boundary.",
        )
        self.assertNotIn(
            ("vp_perfect_clausal_zero_complement",
             "have said the captain was weak, and indeed he seemed "
             "rather to grow weaker than regain his strength"), spans,
        )

        for positive in (
            "I have said Mary was kind, and indeed John came.",
            "I have said that Mary was kind, and indeed John came.",
        ):
            with self.subTest(positive=positive):
                analyzed = p.parse(positive, diagnostic_k=32).result
                self.assertTrue(analyzed.completed, analyzed.stats)
                root = analyzed.best()
                self.assertIsNotNone(root)
                assert root is not None

                def spans(node):
                    yield (node.rule_id, positive[node.start:node.end])
                    for child in node.children:
                        yield from spans(child)

                observed = set(spans(root))
                expected_report = (
                    "have said that Mary was kind"
                    if "said that" in positive else "have said Mary was kind"
                )
                expected_rule = (
                    "vp_perfect_clausal_that_complement"
                    if "said that" in positive
                    else "vp_perfect_clausal_zero_complement"
                )
                self.assertIn((expected_rule, expected_report), observed)
                self.assertIn(
                    ("clause_comma", positive.rstrip(".")), observed,
                    "The discourse marker is outside the reported proposition.",
                )

        for negative in (
            "Mary opened the door, and indeed John came.",
            "I have said Mary was kind, and John came.",
        ):
            with self.subTest(negative=negative):
                analyzed = p.parse(negative, diagnostic_k=32).result
                self.assertFalse(
                    analyzed.stats.get("matrix_discourse_tiebreak_applied", False),
                    "A non-reporting VP or absent discourse marker cannot trigger the tie-break.",
                )

    def test_modal_perfect_composes_with_lexically_typed_bare_predicates(self):
        p = make_parser()
        positives = (
            ("Mary would have answered the question.",
             "vpnp_base_perfect_transitive"),
            ("John could have written a letter.",
             "vpnp_base_perfect_transitive"),
            ("Mary might have arrived.",
             "vpnp_base_perfect_intransitive"),
        )
        for sentence, constituent in positives:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence, diagnostic_k=32).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertIn(
                    constituent, set(self.rule_ids(parsed.best())),
                    (sentence, constituent, parsed.stats),
                )
                self.assertIn(
                    "vp_modal_bare", set(self.rule_ids(parsed.best())),
                    (sentence, parsed.stats),
                )

        for sentence in (
            "Mary would have the question.",
            "Mary might have an arrival.",
        ):
            with self.subTest(unlicensed=sentence):
                parsed = p.parse(sentence, diagnostic_k=32).result
                self.assertFalse(any(
                    {"vpnp_base_perfect_transitive",
                     "vpnp_base_perfect_intransitive"}
                    & set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=32)
                ), sentence)

    def test_original_novel_cases_preserve_key_structural_distinctions(self):
        p = make_parser()
        cases = (
            (
                "The materials at present within my command hardly appeared "
                "adequate to so arduous an undertaking, but I doubted not "
                "that I should ultimately succeed.",
                {"np_prenominal_degree_adjective_indefinite_noun",
                 "vp_finite_clausal_not_that"},
                set(),
            ),
            (
                "Foraging about, I found a bottle with some brandy left, "
                "for Hands.",
                {"clause_front_participial_adverb",
                 "clause_final_comma_benefactive_pp"},
                set(),
            ),
            (
                "I have said the captain was weak, and indeed he seemed "
                "rather to grow weaker than regain his strength.",
                {"vp_perfect_clausal_zero_complement",
                 "clause_initial_coordinator_discourse_adverb"},
                {"np_coord_adv"},
            ),
        )
        for sentence, required, prohibited in cases:
            with self.subTest(sentence=sentence):
                result = p.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertIsNotNone(root)
                realized = set(self.rule_ids(root))
                self.assertFalse(required - realized, (required - realized, realized))
                self.assertFalse(prohibited & realized, prohibited & realized)

    def test_fronted_participle_with_adverb_and_detached_beneficiary(self):
        p = make_parser()
        examples = (
            ("Foraging about, I found a bottle.",
             "clause_front_participial_adverb"),
            ("I saved a seat, for Mary.",
             "clause_final_comma_benefactive_pp"),
        )
        for sentence, expected_rule in examples:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertTrue(any(
                    expected_rule in set(self.rule_ids(root))
                    for root in parsed.alternatives(limit=8)
                ), expected_rule)


class SegmentationTests(unittest.TestCase):
    def test_lexicalized_placeholder_name_keeps_external_copula_and_other_readings(self):
        p = make_parser()
        for text in (
            "Old what’s-his-name’s in a bad way.",
            "Old what's-his-name's in a bad way.",
            "I met who's-her-name yesterday.",
            "I met what's-their-name yesterday.",
        ):
            with self.subTest(text=text):
                lattice = p.parse(text).lattice
                edges = [
                    c for c in lattice.candidates
                    if c.source == "lexicalized-placeholder-name"
                ]
                self.assertEqual(len(edges), 1, text)
                edge = edges[0]
                self.assertEqual(edge.category, "N")
                self.assertEqual(edge.lemma, "whats-his-name")
                self.assertEqual(edge.features.as_dict().get("number"), "singular")
                self.assertTrue(text[edge.span_start:edge.span_end].endswith("-name"))
                self.assertEqual(edge.surface, text[edge.span_start:edge.span_end])
                # Apostrophe inside the name remains visible as an ordinary
                # tokenization alternative instead of mutating source text.
                self.assertTrue(any(
                    c.category in {"WH-NOM", "WH-PRONOUN"}
                    for c in lattice.candidates
                    if c.span_start >= edge.span_start
                    and c.span_end <= edge.span_end
                ))

        for example in ("what-is-his-name", "what's-his-house"):
            lattice = p.parse(example + " was here.").lattice
            self.assertFalse(any(
                c.source == "lexicalized-placeholder-name"
                for c in lattice.candidates
            ), example)


    def test_bare_linking_predicates_require_lexical_linking_valency(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        for text in ("Mary might become happy.", "John can become tired."):
            with self.subTest(text=text):
                result = p.parse(text).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(any(
                    "vpnp_base_linking_adjective_phrase" in set(rules(root))
                    for root in result.alternatives(limit=8)
                ))

        for text in ("Mary might eat happy.", "John can run blue."):
            with self.subTest(unlicensed=text):
                result = p.parse(text).result
                self.assertFalse(any(
                    "vpnp_base_linking_adjective_phrase" in set(rules(root))
                    for root in result.alternatives(limit=8)
                ))

    def test_yet_preserves_adverb_and_adds_adversative_coordination(self) -> None:
        parser = make_parser()
        lattice = parser.parse("Mary was happy yet worried.").lattice
        readings = [candidate for candidate in lattice.candidates
                    if candidate.surface.casefold() == "yet"]
        self.assertIn("COORD", {candidate.category for candidate in readings})
        self.assertIn("ADV", {candidate.category for candidate in readings})
        self.assertTrue(any(
            c.category == "COORD"
            and c.features.as_dict().get("adversative") == "true"
            for c in readings
        ))
        result = parser.parse("Mary was happy yet worried.").result
        self.assertTrue(result.completed, result.stats)
        # The adjective coordination must be a licensed lexical reading;
        # equivalent complete roots need not choose identical ranking.
        def descendants(node):
            yield node
            for child in node.children:
                yield from descendants(child)
        self.assertTrue(any(
            "adjp_coord" in {node.rule_id for node in descendants(root)}
            for root in result.alternatives(limit=8)
        ))

    def test_zero_relative_perfect_preserves_auxiliary_and_real_verb(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        for sentence in (
            "Mary met the author John had praised.",
            "The letters John had written were useful.",
        ):
            with self.subTest(sentence=sentence):
                result = p.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertIsNotNone(root)
                # The overt relative or that-clause may have competing
                # grammatical analyses; the licensed perfect object gap
                # must remain available among the packed derivations.
                alternatives = result.alternatives(limit=12)
                self.assertTrue(any(
                    "wh_bare_perfect_object_relative" in set(rules(node))
                    for node in alternatives
                ), [node.rule_id for node in alternatives])

        # The gap cannot be licensed by an intransitive participle or
        # an auxiliary whose surface contradicts its subject agreement.
        for sentence in (
            "Mary met the author John had arrived.",
            "Mary met the author John have praised.",
        ):
            with self.subTest(unlicensed=sentence):
                parsed = p.parse(sentence).result
                self.assertFalse(any(
                    "wh_bare_perfect_object_relative" in set(rules(node))
                    for node in parsed.alternatives(limit=12)
                ))

    def test_serial_nominal_subject_and_negative_perfect_compose(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        simple = p.parse("My old dog arrived.").result
        self.assertTrue(simple.completed, simple.stats)
        # The established N->ADJ N + possessive NP tree is equally valid.
        # Test the new full ADJP construction in the serial-subject tree below.

        perfect = p.parse("She had not yet found the box.").result
        self.assertTrue(perfect.completed, perfect.stats)
        self.assertIn("vp_perfect_negated_adverbial_transitive",
                      set(rules(perfect.best())))

        sentence = (
            "Her house and her barn, her books and her letters, "
            "and all their old toys, had not yet lost their value."
        )
        result = p.parse(sentence).result
        self.assertTrue(result.completed, result.stats)
        root = result.best()
        self.assertEqual(root.rule_id,
                         "clause_serial_nominal_subject_comma_predicate")
        observed = set(rules(root))
        self.assertIn("np_serial_third_person_nominal_coordination", observed)
        self.assertIn("np_universal_third_person_nominal", observed)
        self.assertIn("vp_perfect_negated_adverbial_transitive", observed)

        # A simple uncoordinated subject does not license the punctuation
        # merely by satisfying common-noun features.
        plain = p.parse("The dog, barks.").result
        for root in plain.alternatives(limit=8):
            self.assertNotIn(
                "clause_serial_nominal_subject_comma_predicate",
                set(rules(root)),
            )

    def test_shared_subject_coordination_across_conjunct_adjunct(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        cases = (
            ("John waited, and in frustration, opened the box.",
             "vp_finite_comma_coord_fronted_pp"),
            ("Mary waited, and suddenly, opened the door.",
             "vp_finite_comma_coord_fronted_adv"),
        )
        for sentence, expected in cases:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertIn(expected, set(rules(parsed.best())))

    def test_interpolated_modal_reporting_requires_reporting_verb(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        for sentence in (
            "John, I may observe, opened the box.",
            "Mary, I might add, arrived.",
            "Peter, I may remark, waited patiently.",
        ):
            with self.subTest(sentence=sentence):
                result = p.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertIn(
                    "parenthetical_reporting_modal_bare",
                    set(rules(result.best())),
                )
        for sentence in (
            "John, I may eat, opened the box.",
            "Mary, I might swim, arrived.",
        ):
            with self.subTest(unlicensed=sentence):
                result = p.parse(sentence).result
                for root in result.alternatives(limit=8):
                    self.assertNotIn(
                        "parenthetical_reporting_modal_bare",
                        set(rules(root)),
                    )

    def test_literary_question_and_habitual_trees_are_licensed(self) -> None:
        parser = make_parser()

        def derivations(node):
            yield node.rule_id
            for child in node.children:
                yield from derivations(child)

        cases = (
            ("What brings you here, man?", "clause_wh_subject_question_vocative"),
            ("Dick, was it?", "clause_copular_left_dislocation_question"),
            ("And when you used to tell the stories?", "vp_past_habitual_used_to"),
            ("I've half a mind to dine first.", "vp_possessive_have_np_infinitival_modifier"),
        )
        for sentence, expected in cases:
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertIsNotNone(root)
                self.assertIn(expected, set(derivations(root)))

    def test_british_directional_towards_keeps_preposition_and_wordnet(self) -> None:
        p = make_parser()
        lattice = p.parse("She moved towards the door.").lattice
        readings = [c for c in lattice.candidates
                    if c.surface.casefold() == "towards"]
        self.assertIn("PREP", {c.category for c in readings})
        self.assertTrue(any(c.lemma == "toward" for c in readings
                            if c.category == "PREP"))
        self.assertIn("PREP", {c.category for c in p.parse(
            "She moved toward the door.").lattice.candidates
            if c.surface.casefold() == "toward"})

    def test_quoted_exclamation_with_iterated_adverbial_has_true_structure(self) -> None:
        parser = make_parser()
        text = '"Darby M\'Graw!" again and again and again.'
        parsed = parser.parse(text).result
        self.assertTrue(parsed.completed, parsed.stats)
        best = parsed.best()
        self.assertEqual(best.rule_id,
                         "clause_direct_speech_iterative_reporting_ellipsis")
        self.assertEqual([node.category for node in best.children],
                         ["DIRECT-SPEECH", "ADVP"])
        self.assertEqual(best.children[1].rule_id,
                         "advp_iterative_recursive_coordination")

    def test_negative_copular_distance_keeps_numeral_and_reference_pp(self) -> None:
        parser = make_parser()
        parsed = parser.parse(
            "I was not a hundred yards from her when the wind came again in a clap."
        ).result
        self.assertTrue(parsed.completed, parsed.stats)
        best = parsed.best()
        self.assertEqual(best.rule_id, "clause_when_post")
        assert best is not None
        self.assertIn(
            "vp_copular_negated_measure_pp",
            {n.rule_id for n in self._descendants_for_test(best)}
        )

    @staticmethod
    def _descendants_for_test(item):
        yield item
        for child in item.children:
            yield from SegmentationTests._descendants_for_test(child)

    def test_predicative_inversion_free_relatives_keep_genuine_subjects(self) -> None:
        p = make_parser()
        examples = (
            ("Such is my journal of what relates to this strange occurrence "
             "up to the present day.",
             {"clause_predicative_adjp_copular_inversion",
              "np_nominal_free_relative_subject"}),
            ("and still different from either was what Mr. Bennet sent to Mr. Collins, "
             "in reply to his last.",
             {"clause_predicative_adjp_copular_inversion",
              "np_nominal_free_relative_object_pp",
              "np_free_relative_supplementary_pp"}),
        )
        for sentence, expected in examples:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                root = parsed.best()
                self.assertIsNotNone(root)
                descendants = [root]
                for item in descendants:
                    descendants.extend(item.children)
                realized = {node.rule_id for node in descendants}
                self.assertTrue(expected <= realized, (expected, realized))

    def test_distributive_either_and_neither_keep_nominal_alternatives(self) -> None:
        p = make_parser()
        for word in ("either", "neither"):
            with self.subTest(word=word):
                lexical = {c.category for c in p.parse(word).lattice.candidates
                           if c.surface.casefold() == word}
                self.assertIn("DET", lexical)
                self.assertIn("PRONOUN", lexical)

    def test_comparative_elliptical_than_pp_keeps_both_comparison_scopes(self) -> None:
        p = make_parser()
        text = ("When we accosted him, his manner was something more confused, "
                "and something less genteel, than of yore.")
        result = p.parse(text).result
        self.assertTrue(result.completed, result.stats)
        root = result.best()
        self.assertEqual(root.rule_id, "clause_when_comma")
        visited = [root]
        for item in visited:
            visited.extend(item.children)
        rules = {item.rule_id for item in visited}
        self.assertIn("np_coordinated_comparative_predicatives", rules)
        self.assertIn("np_comparative_elliptical_than_pp", rules)
        assert sum(item.rule_id == "np_indefinite_pronoun_comparative_adj"
                   for item in visited) == 2

    def test_more_less_comparative_degree_preserves_wordnet_adverbs(self) -> None:
        p = make_parser()
        for word in ("more", "less"):
            with self.subTest(word=word):
                candidates = [
                    c for c in p.parse(word).lattice.candidates
                    if c.surface.casefold() == word
                ]
                self.assertTrue(any(c.category == "DEGREE" and
                                    c.features.as_dict().get("comparative") == "true"
                                    for c in candidates))
                self.assertIn("ADV", {c.category for c in candidates})

    def test_internal_apostrophe_surnames_are_full_span_names(self) -> None:
        parser = make_parser()
        for surface in ("O'Brien", "D'Artagnan", "M'Graw", "O’Connor"):
            with self.subTest(surface=surface):
                lattice = parser.parse(surface).lattice
                names = [c for c in lattice.candidates
                         if c.span_start == 0 and c.span_end == len(surface)
                         and c.category == "PROPER-NOUN"]
                self.assertTrue(names, surface)
                self.assertTrue(
                    any(c.source == "proper-noun-apostrophe" for c in names),
                    [c.as_dict() for c in names],
                )
        for contraction in ("I've", "John's", "We'd"):
            with self.subTest(contraction=contraction):
                lattice = parser.parse(contraction).lattice
                self.assertFalse(any(
                    c.category == "PROPER-NOUN"
                    and c.span_start == 0 and c.span_end == len(contraction)
                    and c.source == "proper-noun-apostrophe"
                    for c in lattice.candidates
                ))

    def test_send_true_double_object_is_not_donate_double_object(self) -> None:
        parser = make_parser()

        def rule_ids(node):
            yield node.rule_id
            for child in node.children:
                yield from rule_ids(child)

        for sentence in ("Peter sent Susan a message.",
                         "Mary sent John a letter.",
                         "They sent her the manuscript."):
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertIn("vp_ditransitive", set(rule_ids(result.best())))

        # Donate selects a prepositional recipient instead. In particular
        # an ambiguous unrelated noun-compound analysis is NOT evidence
        # for donation's ditransitive lexical frame.
        for sentence in ("They donated John a book.",
                         "She donated Mary a painting."):
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence).result
                if result.best() is not None:
                    self.assertNotIn("vp_ditransitive",
                                     set(rule_ids(result.best())))
        grammatical = parser.parse("They donated a book to John.").result
        self.assertTrue(grammatical.completed, grammatical.stats)

    def test_habitual_used_and_fractional_half_keep_open_class_readings(self) -> None:
        parser = make_parser()
        for word, specialty, lexical in (
            ("used", "HABITUAL", "V"),
            ("half", "DET", "N"),
        ):
            with self.subTest(word=word):
                candidates = [
                    c for c in parser.parse(word).lattice.candidates
                    if c.surface.casefold() == word
                ]
                categories = {c.category for c in candidates}
                self.assertIn(specialty, categories)
                self.assertIn(lexical, categories)

    def test_lattice_has_candidates(self) -> None:
        lexicon = load_lexicon(DATA / "lexicon.jsonl")
        lattice = build_lattice("John opened the box.", lexicon)
        self.assertGreater(len(lattice.candidates), 4)
        surfaces = {c.surface for c in lattice.candidates}
        self.assertIn("John", surfaces)
        self.assertIn("opened", surfaces)
        self.assertIn("the", surfaces)
        self.assertIn("box", surfaces)

    def test_multiword_overlap_preserved(self) -> None:
        lexicon = load_lexicon(DATA / "lexicon.jsonl")
        lattice = build_lattice("John found a box.", lexicon)
        # At least the proper-noun and lexicon hypotheses must coexist.
        john = [c for c in lattice.candidates if c.surface == "John"]
        self.assertGreaterEqual(len(john), 1)

    def test_independent_wh_subject_question_needs_question_boundary(self) -> None:
        """A relative fragment must not be rescued by a lexical homograph."""
        parser = make_parser()
        fragment = "which I accordingly did"
        result = parser.parse(fragment).result
        self.assertFalse(result.completed, result.stats)
        self.assertIsNone(result.best())

        # Ordinary questions retain their nominal wh constructions, while
        # the proper noun/letter-N interpretation of I remains lexical.
        for question in ("Who arrived?", "Which guests arrived?"):
            with self.subTest(question=question):
                parsed = parser.parse(question).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertEqual(parsed.best().rule_id, "clause_wh_subj")
        lattice = parser.parse(fragment).lattice
        self.assertIn("N", {c.category for c in lattice.candidates
                            if c.surface == "I"})
        self.assertIn("PRONOUN", {c.category for c in lattice.candidates
                                  if c.surface == "I"})

    def test_local_irregular_inflection_does_not_hide_wordnet_verb(self) -> None:
        """A local auxiliary and an irregular lexical verb are both real."""
        parser = make_parser()
        for surface in ("did", "does"):
            with self.subTest(surface=surface):
                lattice = parser.parse(f"John {surface} the work.").lattice
                readings = [candidate for candidate in lattice.candidates
                            if candidate.surface.lower() == surface]
                self.assertTrue(any(c.category == "AUX" for c in readings))
                self.assertTrue(any(
                    c.category == "V" and c.lemma == "do"
                    and c.features.as_dict().get("vform") == "finite"
                    and any(i.sense_id and i.sense_id.startswith("wn-")
                            for i in c.interpretations)
                    for c in readings
                ), [c.as_dict() for c in readings])

        lexical = parser.parse("John did the work.").result
        self.assertTrue(lexical.completed, lexical.stats)
        best = lexical.best()
        self.assertIsNotNone(best)
        def rules(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in rules(child)
            }
        self.assertIn("vp_transitive", rules(best))

        auxiliary = parser.parse("John did not open the box.").result
        self.assertTrue(auxiliary.completed, auxiliary.stats)
        self.assertIn("clause_neg_vp", rules(auxiliary.best()))


class MorphologyAndNominalAgreementRegressionTests(unittest.TestCase):
    """Tests across lexical, morphology, composition and sentence levels."""

    def test_did_has_finite_but_not_past_participle_reading(self) -> None:
        p = make_parser()
        did = [c for c in p.parse("John did the work.").lattice.candidates
               if c.surface == "did" and c.category == "V"]
        self.assertIn("finite", {c.features.as_dict().get("vform") for c in did})
        self.assertNotIn("ed", {c.features.as_dict().get("vform") for c in did})
        done = [c for c in p.parse("The work was done.").lattice.candidates
                if c.surface == "done" and c.category == "V"]
        self.assertIn("ed", {c.features.as_dict().get("vform") for c in done})
        self.assertNotIn("finite", {c.features.as_dict().get("vform") for c in done})

    def test_unlicensed_past_participle_cannot_make_pronoun_nominal(self) -> None:
        p = make_parser()
        for text in ("They did opened the door.",
                     "She did not opened the door."):
            with self.subTest(text=text):
                result = p.parse(text).result
                self.assertFalse(result.completed, result.stats)
        self.assertTrue(p.parse("They did open the door.").result.completed)
        self.assertTrue(p.parse("She did not open the door.").result.completed)

    def test_common_noun_subject_is_third_person(self) -> None:
        p = make_parser()
        wrong = p.parse("The boy are happy.").result
        self.assertFalse(wrong.completed, wrong.stats)
        self.assertFalse(p.parse("The books is heavy.").result.completed)
        self.assertTrue(p.parse("The boy is happy.").result.completed)
        self.assertTrue(p.parse("You are happy.").result.completed)
        self.assertTrue(p.parse("They are happy.").result.completed)
        self.assertTrue(p.parse("John must be happy.").result.completed)

class ChartParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = make_parser()

    def test_transitive_clause(self) -> None:
        report = self.parser.parse("John opened the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best.category, "CLAUSE")
        self.assertEqual(best.start, 0)

    def test_semantic_roles_on_transitive(self) -> None:
        report = self.parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        semantic = report.interpret(best)
        relations = {edge.relation for edge in semantic.graph.relations}
        self.assertIn("AGENT", relations)
        # Object role name comes from the WordNet verb frame mapping
        # (THEME or AFFECTED depending on the frame).
        self.assertTrue(relations & {"AFFECTED", "THEME"}, relations)

    def test_ditransitive_clause(self) -> None:
        report = self.parser.parse("John gave Mary the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        assert best is not None
        semantic = report.interpret(best)
        relations = {edge.relation for edge in semantic.graph.relations}
        self.assertIn("RECIPIENT", relations)
        self.assertIn("THEME", relations)

    def test_copula_adjective(self) -> None:
        report = self.parser.parse("Mary is happy.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_intransitive(self) -> None:
        report = self.parser.parse("John left.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_pied_piped_relative_pp_is_a_headed_np(self) -> None:
        """A preposition plus an oblique wh-word modifies a real NP head."""
        examples = (
            ("The shore on which Mary stood was quiet.",
             "np_relative_pp_restrictive"),
            ("The sea, on which the moon shone, was calm.",
             "np_relative_pp_comma_pair"),
            ("The question to which Mary replied was difficult.",
             "np_relative_pp_restrictive"),
            ("The students, of whose work Mary spoke, waited.",
             "np_relative_pp_comma_pair"),
        )
        def descendants(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in descendants(child)
            }
        for sentence, rule in examples:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                best = parsed.best()
                self.assertIsNotNone(best)
                self.assertIn(rule, descendants(best))

    def test_pied_piping_cannot_be_invented_from_any_wh_or_prep(self) -> None:
        """Reject missing relative pronouns and unlicensed possessive gaps."""
        def descendants(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in descendants(child)
            }
        for sentence in (
            "The shore on Mary stood was quiet.",
            "The shore on what Mary stood was quiet.",
            "The students, of whose Mary spoke, waited.",
            "The shore on which Mary.",
        ):
            with self.subTest(sentence=sentence):
                best = self.parser.parse(sentence).result.best()
                if best is not None:
                    self.assertFalse(
                        any(rule is not None and rule.startswith("np_relative_pp")
                            for rule in descendants(best)),
                        sentence,
                    )
        control = self.parser.parse("Mary stood on the shore.").result.best()
        self.assertIsNotNone(control)
        self.assertFalse(
            any(rule is not None and rule.startswith("np_relative_pp")
                for rule in descendants(control))
        )

    def test_predicative_adjectives_license_finite_content_clauses(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        cases = (
            ("Mary is sure John will return.", "adjp_clausal_bare"),
            ("Mary is sure that John will return.", "adjp_clausal_that"),
            ("Mary is afraid John will leave.", "adjp_clausal_bare"),
            ("Mary is glad that John will return.", "adjp_clausal_that"),
            ("Are you quite sure that you can go?", "adjp_degree_clausal"),
        )
        for text, required in cases:
            with self.subTest(text=text):
                parsed = self.parser.parse(text).result
                self.assertTrue(parsed.completed, parsed.stats)
                trees = [tree for tree in parsed.alternatives(limit=64)]
                self.assertTrue(
                    any(required in rule_ids(tree) for tree in trees),
                    (text, parsed.stats, [tree.rule_id for tree in trees]),
                )

    def test_clausal_adjective_valency_excludes_generic_adjectives(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        for text in (
            "Mary is tall John will return.",
            "Mary is blue that John returned.",
            "Are you quite tall that John returned?",
        ):
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                for tree in result.alternatives(limit=8):
                    self.assertNotIn("adjp_clausal_bare", rule_ids(tree))
                    self.assertNotIn("adjp_clausal_that", rule_ids(tree))
        # Existing ordinary adjectival predication remains available.
        basic = self.parser.parse("Mary is sure.").result
        self.assertTrue(basic.completed, basic.stats)

    def test_discourse_parentheticals_inside_finite_clauses(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        sentences = (
            ("Mary, however, opened the box.", "clause_subject_parenthetical_vp"),
            ("Mary, indeed, left.", "clause_subject_parenthetical_vp"),
            ("John tried, therefore, to open the box.",
             "vp_subject_control_parenthetical_inf"),
        )
        for text, expected in sentences:
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(
                    any(expected in rule_ids(tree)
                        for tree in result.alternatives(limit=24)),
                    (text, result.stats),
                )

    def test_discourse_parenthetical_cannot_swallow_plain_adverbs(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        for text in (
            "Mary, quickly, opened the box.",
            "Mary however opened the box.",
            "Mary, however opened the box.",
            "John kicked, therefore, to open the box.",
        ):
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                for tree in result.alternatives(limit=16):
                    rule_set = rule_ids(tree)
                    self.assertNotIn("clause_subject_parenthetical_vp", rule_set)
                    self.assertNotIn("vp_subject_control_parenthetical_inf", rule_set)

    def test_subject_supplementary_adjective_between_commas(self) -> None:
        """An ADJP adjunct must not erase the subject's finite agreement."""
        def ids(node):
            return {node.rule_id} | {key for child in node.children for key in ids(child)}
        positives = (
            "The Turk, amazed and delighted, endeavoured to kindle the zeal of his deliverer by promises of reward and wealth.",
            "The scientist, exhausted and hungry, returned home.",
            "Mary, tired, opened the box.",
        )
        for sentence in positives:
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(
                    any("clause_subject_parenthetical_adjp_referential" in ids(tree)
                        for tree in result.alternatives(limit=24)),
                    (sentence, result.stats),
                )

    def test_subject_supplementary_adjective_requires_adjp_and_two_commas(self) -> None:
        def ids(node):
            return {node.rule_id} | {key for child in node.children for key in ids(child)}
        for sentence in (
            "The scientist, and hungry, returned home.",
            "The scientist, opened the box, returned home.",
            "The scientist, hungry returned home.",
            "The scientist hungry, returned home.",
            "The scientist, Mary, returned home.",
        ):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                for tree in result.alternatives(limit=16):
                    self.assertFalse("clause_subject_parenthetical_adjp_referential" in ids(tree))

    def test_parenthetical_adjective_cannot_invent_bare_subjects(self) -> None:
        """Reject bare count nouns and spurious noun readings in incidentals."""
        def walk(item):
            yield item
            for child in item.children:
                yield from walk(child)

        negative_corpus = (
            "I could only sit down before my fire, biting the key of my carpet-bag, and think of the captivating, girlish, bright-eyed lovely Dora.",
            '"You were thrown, by some surprising accident, on this shore, renowned for its hospitality, seized immediately, and charged with murder."',
        )
        for text in negative_corpus:
            with self.subTest(text=text):
                parsed = self.parser.parse(text, max_items=50000,
                                           kbest_work_limit=500000).result
                for tree in parsed.alternatives(limit=2):
                    for node in walk(tree):
                        if node.rule_id == "clause_subject_parenthetical_adjp_referential":
                            self.assertNotIn(
                                text[node.children[0].start:node.children[0].end],
                                {"shore", "think of the captivating"},
                            )

    def test_recovered_turk_clause_anchors_its_correct_subject(self) -> None:
        sentence = '"The Turk, amazed and delighted, endeavoured to kindle the zeal of his deliverer by promises of reward and wealth."'
        best = self.parser.parse(sentence).result.best()
        self.assertIsNotNone(best)
        spoken = best.children[0]
        self.assertEqual(spoken.category, "DIRECT-SPEECH")
        clause = next(child for child in spoken.children if child.category == "CLAUSE")
        self.assertEqual(clause.rule_id, "clause_subject_parenthetical_adjp_referential")
        subject, _, adjunct, _, predicate = clause.children
        self.assertEqual(sentence[subject.start:subject.end], "The Turk")
        self.assertEqual(sentence[adjunct.start:adjunct.end], "amazed and delighted")
        self.assertTrue(sentence[predicate.start:predicate.end].startswith("endeavoured to"))

    def test_second_person_agreement_retains_both_be_number_readings(self) -> None:
        """Are/were must license 2sg you, without making 3sg he agree."""
        from seman_parser.segmentation import build_lattice
        lexicon = self.parser.resources.lexicon
        for surface in ("are", "were"):
            with self.subTest(surface=surface):
                lattice = build_lattice(surface, lexicon)
                readings = [
                    c.features.as_dict()
                    for c in lattice.candidates
                    if c.category == "AUX-BE"
                ]
                self.assertTrue(any(
                    f.get("number") == "singular" and f.get("person") == "2"
                    for f in readings
                ), readings)
                self.assertTrue(any(
                    f.get("number") == "plural" for f in readings
                ), readings)
        self.assertTrue(self.parser.parse("You are happy.").result.completed)
        self.assertTrue(self.parser.parse("You were captured.").result.completed)

    def test_shared_auxiliary_rejects_third_person_singular_were(self) -> None:
        def rules(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in rules(child)
            }
        parsed = self.parser.parse("He were captured, and released.").result
        for tree in parsed.alternatives(limit=20):
            self.assertNotIn("vp_passive_shared_aux_sequence", rules(tree))

    def test_shared_finite_auxiliary_in_passive_participle_series(self) -> None:
        """The coordinated verbs share one finite passive auxiliary."""
        def walk(node):
            yield node
            for child in node.children:
                yield from walk(child)
        cases = (
            "The doors were opened, and closed.",
            "The prisoners were questioned, and released.",
            "The parcel was wrapped, and delivered.",
            "You were thrown, by some surprising accident, on this shore, renowned for its hospitality, seized immediately, and charged with murder.",
        )
        for sentence in cases:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence, max_items=50000,
                                           kbest_work_limit=500000).result
                self.assertTrue(parsed.completed, parsed.stats)
                alternatives = parsed.alternatives(limit=12)
                self.assertTrue(any(
                    any(n.rule_id == "vp_passive_shared_aux_sequence" for n in walk(tree))
                    for tree in alternatives
                ), (sentence, parsed.stats))

    def test_complex_shared_aux_passive_is_best_and_preserves_np_attachment(self) -> None:
        """Check the internal *tree*, not merely a completed root."""
        sentence = (
            "You were thrown, by some surprising accident, on this shore, "
            "renowned for its hospitality, seized immediately, "
            "and charged with murder."
        )
        parsed = self.parser.parse(
            sentence, max_items=50000, kbest_work_limit=500000,
        ).result
        best = parsed.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.rule_id, "clause_passive", parsed.stats)

        def nodes(item):
            yield item
            for child in item.children:
                yield from nodes(child)
        rules = {item.rule_id for item in nodes(best)}
        self.assertIn("vp_passive_shared_aux_sequence", rules)
        self.assertIn("np_postposed_supplementary_adjp", rules)
        adjunct = next(
            n for n in nodes(best)
            if n.rule_id == "np_postposed_supplementary_adjp"
        )
        self.assertEqual(
            sentence[adjunct.children[2].start:adjunct.children[2].end],
            "renowned for its hospitality",
        )
        self.assertNotIn("pp_np_coord", rules)
        self.assertNotIn("clause_subject_parenthetical_adjp_referential", rules)
        self.assertEqual(sentence[best.children[0].start:best.children[0].end],
                         "You")

    def test_np_coordination_disallows_causal_for(self) -> None:
        """Conjunction 'for' joins clauses, not bare nominal objects."""
        parser = self.parser
        parsed = parser.parse("John and Mary opened the box.").result
        self.assertTrue(parsed.completed)
        # The nominal 'and' reading remains legal, without making
        # 'for' a coordinator inside PP objects.
        from seman_parser.engine import Parser
        pp_parser = Parser(parser.resources, goal_category="PP",
                           cache_size=0)
        pp = pp_parser.parse("on this shore, renowned for its hospitality").result
        self.assertTrue(pp.completed, pp.stats)

        def all_nodes(item):
            yield item
            for child in item.children:
                yield from all_nodes(child)

        best = pp.best()
        self.assertEqual(best.rule_id, "pp_prep_np")
        self.assertIn(
            "np_postposed_supplementary_adjp",
            {n.rule_id for n in all_nodes(best)},
        )
        self.assertNotIn(
            "pp_np_coord",
            {n.rule_id for n in all_nodes(best)},
        )

    def test_passive_participle_coordination_requires_real_passives(self) -> None:
        """Do not accept active infinitives or present verbs as passive participles."""
        def rules(node):
            return {node.rule_id} | {r for child in node.children for r in rules(child)}
        negatives = (
            "The doors were open, and close.",
            "The children were happy, and laughed.",
            "The doors opened, and closed.",
            "The doors were opening, and closing.",
        )
        for sentence in negatives:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence).result
                for tree in parsed.alternatives(limit=16):
                    self.assertNotIn("vp_passive_shared_aux_sequence", rules(tree))

    def test_unattested_hyphen_compounds_do_not_invent_verb_lemmas(self) -> None:
        """Preserve POS ambiguity when attested, not via a different word's suffix."""
        from seman_parser.segmentation import build_lattice

        for text, expected in (
            ("bright-eyed", "ADJ"),
            ("carpet-bag", "N"),
        ):
            with self.subTest(compound=text):
                lattice = build_lattice(text, self.parser.resources.lexicon)
                candidates = lattice.covering(0, len(text))
                self.assertTrue(
                    any(c.category == expected for c in candidates),
                    [c.as_dict() for c in candidates],
                )
                unlicensed_verbs = [
                    c for c in candidates
                    if c.category == "V" and c.source == "hyphen-compound"
                ]
                self.assertEqual(unlicensed_verbs, [])

        # Prefixal compounds retain lexically justified verb categories,
        # constrained by the morphology of the attested verbal head.
        prefixed = build_lattice("over-rated", self.parser.resources.lexicon)
        verb_forms = {
            c.features.as_dict().get("vform")
            for c in prefixed.covering(0, len("over-rated"))
            if c.category == "V"
        }
        self.assertIn("ed", verb_forms)
        self.assertTrue(verb_forms.isdisjoint({"base", "ing"}), verb_forms)

        compounds = build_lattice(
            "my carpet-bag and bright-eyed Dora",
            self.parser.resources.lexicon,
        )
        carpet = compounds.covering(3, 13)
        self.assertFalse(any(
            c.category == "N" and c.features.as_dict().get("number") == "plural"
            and c.source == "hyphen-compound" for c in carpet
        ))
        # The legitimate WordNet N and V interpretations of *think*
        # continue to coexist; the restriction applies only to UNATTESTED
        # hyphenated compounds, not individual words.
        think = build_lattice("think", self.parser.resources.lexicon)
        categories = {c.category for c in think.candidates}
        self.assertIn("N", categories)
        self.assertIn("V", categories)

    def test_alternatives_are_preserved(self) -> None:
        report = self.parser.parse("John opened the box.")
        # Even with one preferred reading, the API exposes alternatives.
        alts = report.result.alternatives()
        self.assertGreaterEqual(len(alts), 1)
        self.assertIs(report.result.best(), max(alts, key=lambda i: i.score))

    def test_failed_parse_is_honest(self) -> None:
        # Function words alone cannot form a clause.
        report = self.parser.parse("the the the the.")
        self.assertFalse(report.result.completed)

    def test_provenance_present(self) -> None:
        report = self.parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        payload = best.provenance.as_dict()
        self.assertEqual(payload["source"], "rule")
        self.assertIn("rule_id", payload["detail"])


class ParserCacheTests(unittest.TestCase):
    def test_repeated_parse_reuses_complete_result(self) -> None:
        parser = Parser.from_dir(DATA, cache_size=4)
        first = parser.parse("John opened the box.")
        after_first = parser.cache_stats()
        second = parser.parse("John opened the box.")
        after_second = parser.cache_stats()

        self.assertIs(second.result, first.result)
        self.assertEqual(after_first["parse"]["misses"], 1)
        self.assertEqual(after_first["parse"]["size"], 1)
        self.assertEqual(after_second["parse"]["hits"], 1)

    def test_hierarchical_result_is_cached_too(self) -> None:
        parser = Parser.from_dir(DATA, cache_size=4)
        text = (
            "Mom worked during the day, Dad worked from home, "
            "and Eli learned to read."
        )
        first = parser.parse(text)
        self.assertEqual(first.result.stats.get("engine"), "vector-hierarchical-lazy-kbest")
        second = parser.parse(text)

        self.assertIs(second.result, first.result)
        self.assertEqual(parser.cache_stats()["parse"]["hits"], 1)


class ConstitutionTests(unittest.TestCase):
    """The engine must not encode domain nouns as dispatch."""

    def test_no_domain_identifiers_in_package(self) -> None:
        import ast

        root = Path(__file__).resolve().parents[1] / "seman_parser"
        forbidden = {"requesthandler", "transferevent", "understand_request", "passivesentence"}
        violations: list[str] = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.lower() in forbidden:
                        violations.append(f"{path.name}:{node.lineno}:{node.name}")
                if isinstance(node, ast.If):
                    # No dispatch on literal semantic type / verb names.
                    for child in ast.walk(node.test):
                        if isinstance(child, ast.Compare):
                            for comparator in child.comparators:
                                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                                    if comparator.value.upper() in {"REQUEST", "TRANSFER", "GIVE", "OPEN"}:
                                        violations.append(
                                            f"{path.name}:{node.lineno}:dispatch on {comparator.value!r}"
                                        )
        self.assertEqual(violations, [])



class ProductiveSupplementTests(unittest.TestCase):
    """Full public Parser.parse parses and counterexamples."""

    @staticmethod
    def rule_ids(root):
        if root is None:
            return set()
        return ({root.rule_id} if root.rule_id else set()) | {
            rule for child in root.children
            for rule in ProductiveSupplementTests.rule_ids(child)
        }

    def test_reporting_tag_with_real_participial_adjunct(self):
        result = make_parser().parse(
            "'It was a mistake,' I replied, quietly speaking to the witness."
        ).result
        self.assertIsNotNone(result.best(), result.stats)
        self.assertIn("dialogue_speech_tag_post_participial_adv_pp",
                      self.rule_ids(result.best()))

    def test_comma_and_ing_required_for_reporting_participial_adjunct(self):
        p = make_parser()
        for sentence in (
            "'It was a mistake,' I replied quietly speaking to the witness.",
            "'It was a mistake,' I replied, quietly speak to the witness.",
        ):
            result = p.parse(sentence).result
            for item in result.alternatives(limit=6):
                self.assertNotIn(
                    "dialogue_speech_tag_post_participial_adv_pp",
                    self.rule_ids(item), sentence,
                )

    def test_right_edge_transitive_participial_clause(self):
        result = make_parser().parse(
            "Maya crossed the square, carrying a lantern."
        ).result
        self.assertIsNotNone(result.best(), result.stats)
        self.assertIn("clause_final_transitive_participle", self.rule_ids(result.best()))

    def test_parenthetical_you_know_inside_postpredicate_vp(self):
        result = make_parser().parse(
            "Mary waited, you know, near the entrance."
        ).result
        self.assertIsNotNone(result.best(), result.stats)
        self.assertIn("parenthetical_interpersonal_you_know", self.rule_ids(result.best()))
        self.assertIn("vp_postpredicate_parenthetical", self.rule_ids(result.best()))

    def test_parenthetical_verb_must_be_licensed_and_comma_delimited(self):
        p = make_parser()
        for sentence in (
            "Mary waited, you jump, near the entrance.",
            "Mary waited, you know near the entrance.",
            "Mary waited you know, near the entrance.",
        ):
            result = p.parse(sentence).result
            for item in result.alternatives(limit=6):
                self.assertNotIn(
                    "parenthetical_interpersonal_you_know",
                    self.rule_ids(item), sentence,
                )



class PerfectPassiveMorphologyTests(unittest.TestCase):
    """Perfect-passive auxiliary chains must not reanalyze HAVE as a noun."""

    def test_productive_perfect_passive_with_and_without_negation(self):
        p = make_parser()
        for text in (
            "The door has been opened.",
            "The door has never been opened.",
            "The door had already been opened.",
        ):
            best = p.parse(text).result.best()
            self.assertIsNotNone(best, text)
            root = best
            self.assertEqual(root.rule_id, "clause_passive", text)
            self.assertEqual(root.children[0].category, "NP", text)
            self.assertEqual(text[root.children[0].start:root.children[0].end],
                             "The door", text)
            def tree_rules(node):
                return {node.rule_id} | {r for c in node.children for r in tree_rules(c)}
            self.assertTrue({"vp_perfect_passive", "vp_perfect_passive_adv",
                             "vp_perfect_passive_neg"} & tree_rules(root), text)

    def test_perfect_passive_participle_be_is_not_finite(self):
        p = make_parser()
        result = p.parse("The box has never been opened.")
        be_candidates = [c for c in result.lattice.candidates
                         if c.surface.casefold() == "been" and c.category == "AUX-BE"]
        self.assertIn("ed", {c.features.as_dict().get("vform") for c in be_candidates})
        self.assertIn("finite", {c.features.as_dict().get("vform") for c in be_candidates})



class GreetingVocativeTests(unittest.TestCase):
    """A greeting plus addressee is a dialogue act, not an arbitrary NP."""

    def test_productive_greeting_plus_modified_proper_vocative(self):
        p = make_parser()
        for sentence in ("Adieu, my dear Margaret.", "Hello, our dear Alice.",
                         "Farewell, dear Eleanor."):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            rules = set()
            def collect(node):
                if node.rule_id is not None:
                    rules.add(node.rule_id)
                for child in node.children:
                    collect(child)
            collect(best)
            self.assertIn("clause_farewell_vocative", rules, sentence)
            # A noun-appellation reading ("my dear Margaret") is also
            # lexically possible; do not force the adjective alternative.
            self.assertTrue({"np_poss_adj_proper", "np_poss_n_name", "np_adj_proper"} & rules,
                            sentence)

    def test_salutation_is_required_and_wordnet_noun_alternative_survives(self):
        p = make_parser()
        for sentence in ("River, my dear Margaret.", "Table, dear Eleanor."):
            report = p.parse(sentence)
            for root in report.result.alternatives(limit=8):
                def includes(node):
                    return node.rule_id == "clause_farewell_vocative" or any(
                        includes(child) for child in node.children)
                self.assertFalse(includes(root), sentence)
        lattice = p.parse("Farewell, dear Eleanor.").lattice
        candidates = [c for c in lattice.candidates if c.surface.lower() == "farewell"]
        self.assertIn("INTERJECTION", {c.category for c in candidates})
        self.assertIn("N", {c.category for c in candidates})


class PersonalPronounParadigmTests(unittest.TestCase):
    """Possessive determiner is not a free pronoun, even with WordNet present."""

    def test_we_us_and_our_keep_distinct_grammatical_functions(self):
        p = make_parser()
        samples = {
            "we": {"PRONOUN"},
            "us": {"PRONOUN"},
            "our": {"POSS"},
        }
        for word, expected in samples.items():
            report = p.parse(f"Mary said {word} could help.")
            found = {c.category for c in report.lattice.candidates
                     if c.surface.lower() == word}
            self.assertTrue(expected <= found, (word, found))
            if word == "our":
                self.assertNotIn("PRONOUN", found)

    def test_our_is_available_inside_ordinary_possessive_np(self):
        result = make_parser().parse("Our friends arrived.").result
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        self.assertEqual(best.children[0].category, "NP")
        subject_text = "Our friends arrived."[best.children[0].start:best.children[0].end]
        self.assertEqual(subject_text, "Our friends")


class InterposedAdverbPassiveAndBareControlTests(unittest.TestCase):
    """Productive auxiliary scope and explicit verbal valency."""

    @staticmethod
    def rule_ids(item):
        if item is None:
            return set()
        return ({item.rule_id} if item.rule_id else set()) | {
            rule for child in item.children
            for rule in InterposedAdverbPassiveAndBareControlTests.rule_ids(child)
        }

    def test_interposed_adverb_is_licensed_by_finite_be_and_past_participle(self):
        p = make_parser()
        for text in (
            "The visitor was kindly received.",
            "The children were quickly rescued.",
            "The guest was likewise accommodated with a room.",
        ):
            report = p.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, (text, report.result.stats))
            self.assertIn("vp_passive_interposed_manner_adverb",
                          self.rule_ids(best), text)
            self.assertEqual(best.rule_id, "clause_passive", text)

    def test_non_participle_cannot_fill_passive_slot(self):
        p = make_parser()
        for text in ("The guest was kindly receive.", "The guest was kindly receiving."):
            for item in p.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vp_passive_interposed_manner_adverb",
                                 self.rule_ids(item), text)

    def test_base_subject_control_under_do_support(self):
        p = make_parser()
        for text in (
            "John did not try to leave.",
            "Mary did not attempt to conceal the truth from her friends.",
        ):
            report = p.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, (text, report.result.stats))
            self.assertIn("vpnp_base_subject_control_to_inf",
                          self.rule_ids(best), text)
            self.assertIn(best.rule_id, {"clause_neg", "clause_neg_vp"}, text)

    def test_base_control_requires_lexical_subject_control(self):
        p = make_parser()
        for text in (
            "John did not admire to leave.",
            "John did not smile to leave.",
        ):
            for item in p.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vpnp_base_subject_control_to_inf",
                                 self.rule_ids(item), text)


class NamedEntityNominalConstructionTests(unittest.TestCase):
    """Lexically supported proper-name nominalization and attributive names."""

    @staticmethod
    def rules(item):
        if item is None:
            return set()
        return ({item.rule_id} if item.rule_id else set()) | {
            r for child in item.children
            for r in NamedEntityNominalConstructionTests.rules(child)
        }

    def test_definite_proper_name_with_article(self):
        p = make_parser()
        for sentence in (
            "The Orfling arrived.",
            "The Titanic sank.",
            "The Turk smiled.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            forms = [self.rules(item) for item in report.result.alternatives(limit=8)]
            self.assertTrue(any("np_definite_named_entity" in form for form in forms),
                            (sentence, forms))

    def test_proper_names_can_modify_real_common_noun_heads(self):
        p = make_parser()
        for sentence in (
            "The Longbourn family arrived.",
            "The London train departed.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            self.assertIn("np_determiner_name_noun_compound", self.rules(best), sentence)


    def test_abbreviated_honorific_forms_subject_not_dislocated_topic(self):
        p = make_parser()
        for sentence in (
            "Mr. Gardiner did not attempt to conceal these particulars from the Longbourn family.",
            "Mr. Gardiner smiled.",
            "Mrs. Bennet waited.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            self.assertIn("np_honorific_abbreviation",
                          NamedEntityNominalConstructionTests.rules(best), sentence)
            self.assertNotEqual(best.rule_id, "clause_front_np", sentence)

    def test_abbreviated_honorific_requires_real_title(self):
        p = make_parser()
        result = p.parse("Tree. Alice smiled.")
        for item in result.result.alternatives(limit=8):
            self.assertNotIn("np_honorific_abbreviation",
                             NamedEntityNominalConstructionTests.rules(item))

    def test_indefinite_article_does_not_license_bare_name(self):
        p = make_parser()
        for sentence in ("A Orfling arrived.", "A Titanic sank."):
            report = p.parse(sentence)
            for item in report.result.alternatives(limit=8):
                self.assertNotIn("np_definite_named_entity", self.rules(item), sentence)



class LicensedObjectTopicalizationTests(unittest.TestCase):
    @staticmethod
    def rules(node):
        if node is None:
            return set()
        return ({node.rule_id} if node.rule_id else set()) | {
            rule for child in node.children
            for rule in LicensedObjectTopicalizationTests.rules(child)
        }

    def test_topicalized_object_of_transitive_predicate(self):
        p = make_parser()
        for sentence in (
            "The latter you must develop in her.",
            "The book you must put on the shelf.",
            "The work they can finish.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            self.assertIn("clause_object_topicalization_modal",
                          self.rules(best), sentence)
            self.assertIn("licensed_transitive",
                          dict(best.children[-1].features.as_dict()), sentence)

    def test_modal_topicalization_preserves_gapped_object_and_subordinate_if(self):
        text = "The latter you must develop in her, if you can."
        report = make_parser().parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        self.assertIn("clause_object_topicalization_modal",
                      self.rules(best))

    def test_transitive_verb_is_required_for_object_fronting(self):
        p = make_parser()
        for sentence in ("The rock you must arrive.", "The mountain you can perish."):
            report = p.parse(sentence)
            for root in report.result.alternatives(limit=8):
                self.assertNotIn("clause_object_topicalization_modal",
                                 self.rules(root), sentence)


class SubordinateComplementAgainstDefiniteProperModifierTests(unittest.TestCase):
    def test_complementizer_that_is_not_swallowed_by_name_nominal(self):
        text = "Mary believes that John left."
        report = make_parser().parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        self.assertNotIn("np_determiner_name_noun_compound",
                         NamedEntityNominalConstructionTests.rules(best))
        self.assertIn("John", text[best.start:best.end])

    def test_true_definite_name_noun_still_composes(self):
        text = "The Longbourn family arrived."
        best = make_parser().parse(text).result.best()
        self.assertIsNotNone(best)
        self.assertIn("np_determiner_name_noun_compound",
                      NamedEntityNominalConstructionTests.rules(best))



class AdverbialWhModalAndBarePPTests(unittest.TestCase):
    @staticmethod
    def rules(node):
        if node is None:
            return set()
        return ({node.rule_id} if node.rule_id else set()) | {
            name for child in node.children
            for name in AdverbialWhModalAndBarePPTests.rules(child)
        }

    def test_adverbial_wh_question_and_prepositional_bare_predicate(self):
        p=make_parser()
        for sentence in (
            "Why should I sleep in the garden?",
            "Where can they dwell in the valley?",
            "But why should I dwell upon the incidents that followed this last overwhelming event?",
        ):
            report=p.parse(sentence)
            best=report.result.best()
            self.assertIsNotNone(best,(sentence,report.result.stats))
            self.assertIn("clause_wh_adverbial_modal",self.rules(best),sentence)
            self.assertTrue({"vpnp_bare_intransitive_pp", "vpnp_bare_prepositional_pp"} & self.rules(best), (sentence, self.rules(best)))


    def test_upon_is_real_preposition_with_preserved_lexical_hypotheses(self):
        p=make_parser()
        report=p.parse("John slept upon the ground.")
        cats={c.category for c in report.lattice.candidates if c.surface.casefold()=="upon"}
        self.assertIn("PREP",cats)
        best=report.result.best()
        self.assertIsNotNone(best,report.result.stats)
        rules=self.rules(best)
        self.assertIn("pp_prep_np",rules)

    def test_prepositional_base_predicate_requires_real_valency(self):
        p=make_parser()
        for sentence in ("Why should I depend upon the answer?", "Why should I dwell upon the issue?"):
            report=p.parse(sentence)
            best=report.result.best()
            self.assertIsNotNone(best,report.result.stats)
            self.assertTrue({"vpnp_bare_prepositional_pp", "vpnp_bare_intransitive_pp"} & self.rules(best), (sentence,self.rules(best)))

    def test_an_object_wh_is_not_mistaken_for_adverbial_wh(self):
        p=make_parser()
        for sentence in ("What should I sleep in the garden?", "Which can John sleep in the garden?"):
            report=p.parse(sentence)
            for tree in report.result.alternatives(limit=6):
                self.assertNotIn("clause_wh_adverbial_modal",self.rules(tree),sentence)

    def test_bare_intransitive_pp_does_not_consume_transitive_object(self):
        p=make_parser()
        for sentence in ("Why should I conceal the book?", "Where can we eat the soup?"):
            report=p.parse(sentence)
            for tree in report.result.alternatives(limit=6):
                # These verbs may have other lexical senses, but a real object
                # cannot be swallowed by the intransitive+PP construction.
                for node in tree.children:
                    if node.rule_id=="vpnp_bare_intransitive_pp":
                        self.assertNotIn("the book",sentence[node.start:node.end])


class ClauseSupplementaryCommaPPTests(unittest.TestCase):
    @staticmethod
    def rules(node):
        if node is None:
            return set()
        return ({node.rule_id} if node.rule_id else set()) | {
            r for ch in node.children
            for r in ClauseSupplementaryCommaPPTests.rules(ch)
        }

    def test_compositional_sentence_final_supplementary_pp(self):
        p=make_parser()
        for sentence in (
            "Mary waited, with a look of anxiety.",
            "The road was quiet, with trees along the path.",
            "It was a bitter cold winter, with long, hard frosts and heavy gales.",
        ):
            report=p.parse(sentence)
            best=report.result.best()
            self.assertIsNotNone(best,(sentence,report.result.stats))
            self.assertIn("clause_final_comma_pp_adjunct",self.rules(best),sentence)
            if "long, hard" in sentence:
                self.assertIn("adjp_comma_separated_adjectives",self.rules(best),sentence)

    def test_comma_and_prepositional_phrase_are_both_necessary(self):
        p=make_parser()
        for sentence in ("Mary waited with a look of anxiety.", "Mary waited, the house.", "Mary waited, by the doorway."):
            report=p.parse(sentence)
            for item in report.result.alternatives(limit=8):
                self.assertNotIn("clause_final_comma_pp_adjunct",self.rules(item),sentence)


class EmDashPunctuationProvenanceTests(unittest.TestCase):
    def test_double_hyphen_and_typographic_emdash_have_dash_hypotheses(self):
        parser = make_parser()
        for sentence, marker in (
            ("Anderson's ball--for it was Job--had broken the window.", "--"),
            ("Anderson's ball—for it was Job—had broken the window.", "—"),
        ):
            lattice = parser.parse(sentence).lattice
            spans = {(c.span_start, c.span_end, c.surface, c.category,
                      c.features.as_dict().get("dash_kind"))
                     for c in lattice.candidates if c.surface == marker}
            for position in (sentence.index(marker),
                             sentence.index(marker, sentence.index(marker) + len(marker))):
                self.assertIn((position, position + len(marker), marker,
                               "DASH", "em"), spans)
                self.assertIn((position, position + len(marker), marker,
                               "COMMA", None), spans)

    def test_apostrophe_in_anderson_possessive_is_not_dash(self):
        sentence = "Anderson's ball--for it was Job--had broken the window."
        report = make_parser().parse(sentence)
        dash_spans = [c for c in report.lattice.candidates if c.category == "DASH"]
        self.assertEqual(len(dash_spans), 2)
        self.assertNotIn("'s", [c.surface for c in dash_spans])


class EllipticalOffWithDispatchTests(unittest.TestCase):
    @staticmethod
    def rules(item):
        if item is None:
            return set()
        return ({item.rule_id} if item.rule_id else set()) | {
            rule for child in item.children
            for rule in EllipticalOffWithDispatchTests.rules(child)
        }

    def test_real_dialogue_dispatch_coordinates_with_transitive_imperative(self):
        text = '"Off with you to the cook and get some work."'
        report = make_parser().parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        rules = self.rules(best)
        self.assertIn("clause_elliptical_off_with_np_pp", rules)
        self.assertIn("clause_imperative", rules)
        self.assertIn("vp_bare_trans", rules)
        self.assertIn("clause_coordinate_dispatch_imperative", rules)

        def collect(node):
            result = [(node.rule_id, text[node.start:node.end])]
            for child in node.children:
                result.extend(collect(child))
            return result

        spans = collect(best)
        self.assertIn(("clause_imperative", "get some work"), spans)
        self.assertIn(("vp_bare_trans", "get some work"), spans)
        self.assertIn(("clause_elliptical_off_with_np_pp", "Off with you to the cook"), spans)

    def test_elliptical_dispatch_is_productive_without_the_coordination(self):
        p = make_parser()
        for text in ("Off with you to the cook!", "Off with them to the harbour!",
                     "Off with you!"):
            best = p.parse(text).result.best()
            self.assertIsNotNone(best, text)
            rules = self.rules(best)
            self.assertTrue({"clause_elliptical_off_with_np",
                             "clause_elliptical_off_with_np_pp"} & rules, text)

    def test_off_and_with_are_not_arbitrary_imperative_markers(self):
        p = make_parser()
        for text in ("Across with you to the cook!", "Off beyond you to the cook!"):
            result = p.parse(text)
            for best in result.result.alternatives(limit=8):
                self.assertNotIn("clause_elliptical_off_with_np_pp", self.rules(best), text)
                self.assertNotIn("clause_elliptical_off_with_np", self.rules(best), text)


class LiteraryExceptionDictionaryTests(unittest.TestCase):
    """Attested orthographic variants are first-class lexicon hypotheses."""

    def test_source_attested_hyphenated_words_have_independent_readings(self):
        p = make_parser()
        pairs = (
            ("blood-stained", "ADJ"),
            ("bright-eyed", "ADJ"),
            ("shoulder-blade", "N"),
            ("pick-axe", "N"),
            ("spy-glass", "N"),
            ("charnel-houses", "N"),
            ("well-known", "ADJ"),
            ("stage-cutch", "N"),
            ("carpet-bag", "N"),
        )
        for surface, category in pairs:
            with self.subTest(surface=surface):
                report = p.parse(surface)
                full = report.lattice.covering(0, len(surface))
                matched = [c for c in full
                           if c.category == category
                           and any(i.provenance.get("source") ==
                                   "attested-literary-supplement"
                                   for i in c.interpretations)]
                self.assertTrue(matched, [x.as_dict() for x in full])
                self.assertEqual(matched[0].source, "lexicon-multiword")

    def test_dialectal_words_preserve_attested_spelling_and_normalized_lemma(self):
        lexicon = make_parser().resources.lexicon
        expected = {
            "unfort'nate": ("unfortunate", "ADJ"),
            "howsomever": ("however", "ADV"),
            "sperrits": ("spirit", "N"),
            "sperrit": ("spirit", "N"),
            "babby": ("baby", "N"),
            "cap'n": ("captain", "N"),
            "porkypine": ("porcupine", "N"),
        }
        for surface, (lemma, category) in expected.items():
            with self.subTest(surface=surface):
                matches = lexicon.lookup_morphology(surface)
                self.assertTrue(any(
                    meaning == lemma and sense.category == category
                    and sense.provenance.get("source") ==
                    "attested-literary-supplement"
                    for _, sense, meaning in matches), (surface, matches))

    def test_plural_and_singular_forms_do_not_inherit_each_other(self):
        lexicon = make_parser().resources.lexicon
        for surface, number in (("cross-trees", "plural"),
                                ("school-fellows", "plural"),
                                ("spy-glass", "singular"),
                                ("shoulder-blade", "singular"),
                                ("sperrits", "plural")):
            with self.subTest(surface=surface):
                matches = [(sense.category, sense.features.as_dict().get("number"))
                           for _, sense, _ in lexicon.lookup_morphology(surface)
                           if sense.provenance.get("source") ==
                              "attested-literary-supplement"]
                self.assertIn(("N", number), matches)
                self.assertNotIn(("N", "singular" if number == "plural"
                                  else "plural"), matches)

    def test_distinct_double_dash_does_not_become_hyphenated_word(self):
        p = make_parser()
        text = "Anderson's ball--for it was Job--had broken his shoulder-blade."
        lattice = p.parse(text).lattice
        for c in lattice.candidates:
            if c.source == "lexicon-multiword" and c.surface.count("-") > 0:
                self.assertNotIn("--", c.surface)
        dashes = [c for c in lattice.candidates
                  if c.category == "DASH" and c.surface == "--"]
        self.assertEqual(len(dashes), 2)
        self.assertTrue(any(c.category == "N"
                            and c.surface == "shoulder-blade"
                            for c in lattice.candidates))

    def test_wordnet_and_compound_fallback_remain_available(self):
        p = make_parser()
        for word in ("think", "uninvented-frost", "blood-stained"):
            lattice = p.parse(word).lattice
            self.assertTrue(lattice.candidates, word)
        lattice = p.parse("blood-stained knife").lattice
        self.assertTrue(any(c.source == "lexicon-multiword"
                            and c.surface == "blood-stained"
                            and c.category == "ADJ"
                            for c in lattice.candidates))


class ProductiveHyphenMorphologyWithoutDictionaryTests(unittest.TestCase):
    """Standard hyphenated compounds require no per-word curated entry."""

    @classmethod
    def setUpClass(cls) -> None:
        # Explicitly omit literary_lexicon.jsonl to prove generalization.
        from seman_parser.engine import discover_wordnet
        cls.lexicon = load_lexicon(
            DATA / "function_words.jsonl",
            wordnet_dict=discover_wordnet(DATA),
            supplemental_paths=(DATA / "syntax_lexicon.jsonl",),
            max_senses=8,
        )

    def test_participial_adjectives_productive_without_literary_words(self):
        for word in ("sun-painted", "river-washed", "well-described",
                     "moon-carried"):
            with self.subTest(word=word):
                lattice = build_lattice(word, self.lexicon)
                full = lattice.covering(0, len(word))
                derived = [c for c in full
                           if c.category == "ADJ" and
                           c.source == "hyphen-participial-adjective"]
                self.assertTrue(derived, [c.as_dict() for c in full])
                self.assertTrue(all(
                    any(i.provenance.get("head_lemma") for i in c.interpretations)
                    for c in derived))
                self.assertFalse(any(c.category == "V" and
                                     c.source == "hyphen-participial-adjective"
                                     for c in full))

    def test_headed_nominal_compounds_agree_without_literary_words(self):
        for word, number in (("orchard-bag", "singular"),
                             ("orchard-bags", "plural"),
                             ("hill-trees", "plural")):
            with self.subTest(word=word):
                lattice = build_lattice(word, self.lexicon)
                full = lattice.covering(0, len(word))
                self.assertTrue(any(
                    c.category == "N" and
                    c.features.as_dict().get("number") == number and
                    c.source == "hyphen-compound"
                    for c in full), [c.as_dict() for c in full])

    def test_do_not_fabricate_verbs_or_adjectives_for_unlicensed_heads(self):
        for word in ("carpet-bag", "stone-walk", "silver-cook"):
            with self.subTest(word=word):
                lattice = build_lattice(word, self.lexicon)
                full = lattice.covering(0, len(word))
                self.assertFalse(any(
                    c.source == "hyphen-participial-adjective"
                    for c in full), [c.as_dict() for c in full])
                self.assertFalse(any(
                    c.category == "V" and c.source == "hyphen-compound"
                    for c in full), [c.as_dict() for c in full])

    def test_em_dash_is_never_inside_a_productive_compound(self):
        text = "The sky--for it was night--was sun-painted."
        lattice = build_lattice(text, self.lexicon)
        self.assertTrue(any(
            c.category == "ADJ" and c.surface == "sun-painted"
            for c in lattice.candidates))
        self.assertFalse(any(
            "--" in c.surface and "hyphen" in c.source
            for c in lattice.candidates))


class UnlessConditionalSubordinatorTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from UnlessConditionalSubordinatorTests.nodes(child)

    def test_unless_is_a_subordinator_in_both_cases(self):
        parser = make_parser()
        for text in ("Unless Mary left, John stayed.",
                     "unless Mary left, John stayed.",
                     "John stayed unless Mary left."):
            with self.subTest(text=text):
                report = parser.parse(text)
                candidates = [c for c in report.lattice.candidates
                              if c.surface.casefold() == "unless"
                              and c.category == "CONJ"]
                self.assertTrue(candidates)
                for candidate in candidates:
                    features = candidate.features.as_dict()
                    for forbidden in ("wh", "degree", "complementizer"):
                        self.assertNotIn(forbidden, features)
                best = report.result.best()
                self.assertIsNotNone(best, report.result.stats)
                self.assertTrue(any(n.category == "CONJ"
                                    and text[n.start:n.end].casefold() == "unless"
                                    for n in self.nodes(best)))


    def test_perfect_copular_predicate_requires_base_have_and_participial_be(self):
        parser = make_parser()
        for text in ("John would have been happy.",
                     "Mary might have been quiet and almost invisible."):
            report = parser.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, report.result.stats)
            self.assertIn("vpnp_base_perfect_cop_adjp",
                          {n.rule_id for n in self.nodes(best)})
        for text in ("John would has been happy.",
                     "John would had been happy.",
                     "John would have be happy.",
                     "John would have was happy.",
                     "John would have being happy."):
            report = parser.parse(text)
            for tree in report.result.alternatives(limit=8):
                self.assertNotIn("vpnp_base_perfect_cop_adjp",
                                 {n.rule_id for n in self.nodes(tree)}, text)

    def test_pinned_frankenstein_317_uses_conditional_subordination(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        from scripts.audit_novel_tree_quality import display_tree
        cases, _ = select_cases(500)
        case = cases[317]
        self.assertTrue(case["text"].startswith("Unless I had been animated"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), case, max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        print("UNLESS_317_TREE\n" + "\n".join(
            display_tree(best, prepared.analysis_text)), flush=True)
        nodes = list(self.nodes(best))
        self.assertIn("vpnp_base_perfect_cop_adjp", {n.rule_id for n in nodes})
        self.assertIn("vp_perfect_passive", {n.rule_id for n in nodes})
        self.assertNotIn("clause_modal_ellipsis", {n.rule_id for n in nodes})
        conditional = [n for n in nodes if n.rule_id == "clause_cond"]
        self.assertTrue(conditional, [n.rule_id for n in nodes])
        clause = conditional[0]
        self.assertEqual([n.category for n in clause.children],
                         ["CONJ", "CLAUSE", "COMMA", "CLAUSE"])
        self.assertEqual(prepared.analysis_text[
            clause.children[0].start:clause.children[0].end], "Unless")
        self.assertEqual(prepared.analysis_text[
            clause.children[1].start:clause.children[1].end],
            "I had been animated by an almost supernatural enthusiasm")
        self.assertEqual(prepared.analysis_text[
            clause.children[3].start:clause.children[3].end],
            "my application to this study would have been irksome and almost intolerable")



class SpatialPrepositionsAndObjectAdjectiveTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from SpatialPrepositionsAndObjectAdjectiveTests.nodes(child)

    def test_spatial_prepositions_preserve_other_readings(self):
        parser = make_parser()
        for text in ("Aboard ship", "aboard ship", "round the house"):
            report = parser.parse(text)
            first = report.lattice.tokens[0]
            cats = {c.category for c in report.lattice.covering(first.start, first.end)}
            self.assertIn("PREP", cats)
            self.assertIn("ADV", cats)

    def test_productive_object_adjective_predicate_and_equative_bound(self):
        parser = make_parser()
        for text in ("John can have both hands free.",
                     "Mary could have the room as quiet as possible."):
            with self.subTest(text=text):
                report = parser.parse(text)
                best = report.result.best()
                self.assertIsNotNone(best, report.result.stats)
                self.assertTrue({"vpnp_base_have_object_adjective", "vp_np_resultative"}
                                & {n.rule_id for n in self.nodes(best)})
        report = parser.parse("Mary could have the room as quiet as possible.")
        self.assertIn("adjp_as_as_adjectival_bound",
                      {n.rule_id for n in self.nodes(report.result.best())})
        for text in ("John can sleep both hands free.",
                     "John can had both hands free."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vpnp_base_have_object_adjective",
                                 {n.rule_id for n in self.nodes(tree)}, text)
        for text in ("Mary could have the room as quiet as blue.",
                     "Mary could have the room than quiet as possible."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn("adjp_as_as_adjectival_bound",
                                 {n.rule_id for n in self.nodes(tree)}, text)

    def test_final_infinitival_supplement_requires_overt_boundary(self):
        parser = make_parser()
        text = "Mary waited, to have the room quiet."
        report = parser.parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        self.assertIn("clause_final_comma_infinitival_supplement",
                      {n.rule_id for n in self.nodes(best)})
        for text in ("Mary waited to have the room quiet.",
                     "Mary waited, have the room quiet.",
                     "Mary waited, to had the room quiet."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn("clause_final_comma_infinitival_supplement",
                                 {n.rule_id for n in self.nodes(tree)}, text)

    def test_pinned_treasure_island_445_has_real_object_and_infinitival_supplement(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        from scripts.audit_novel_tree_quality import display_tree
        cases, _ = select_cases(500)
        case = cases[445]
        self.assertTrue(case["text"].startswith("Aboard ship he carried"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), case, max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        print("ABOARD_445_TREE\n" + "\n".join(display_tree(best, text)), flush=True)
        nodes = list(self.nodes(best))
        rules = {n.rule_id for n in nodes}
        self.assertNotIn("clause_infinitive_subject", rules)
        for rule in ("clause_final_comma_infinitival_supplement",
                     "vpnp_base_have_object_adjective",
                     "adjp_as_as_adjectival_bound"):
            self.assertIn(rule, rules)
        spans = {(n.category, text[n.start:n.end]) for n in nodes}
        for expected in (("PP", "Aboard ship"), ("NP", "both hands"),
                         ("ADJ", "possible"), ("NP", "a lanyard round his neck"),
                         ("PP", "round his neck"),
                         ("VP-NP", "have both hands as free as possible")):
            self.assertIn(expected, spans)
        lexical = {(n.category, text[n.start:n.end]) for n in nodes if not n.children}
        self.assertNotIn(("V", "hands"), lexical)
        self.assertNotIn(("N", "possible"), lexical)



class NegatedPossessiveHavePPTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from NegatedPossessiveHavePPTests.nodes(child)

    def test_productive_have_negation_pp_object_and_agreement(self):
        parser = make_parser()
        for text in ("John has not at present any money.",
                     "Mary had not at that time any reason."):
            report = parser.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, report.result.stats)
            self.assertIn("vp_have_neg_pp_object",
                          {n.rule_id for n in self.nodes(best)})
        for text in ("John have not at present any money.",
                     "John had at present any money.",
                     "John slept not at present any money."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vp_have_neg_pp_object",
                                 {n.rule_id for n in self.nodes(tree)}, text)

    def test_any_and_beyond_retain_wordnet_readings(self):
        parser = make_parser()
        for word, wanted in (("any", {"DET", "ADJ", "ADV"}),
                             ("beyond", {"PREP", "ADV"})):
            cats = {c.category for c in parser.parse(word).lattice.candidates}
            self.assertTrue(wanted <= cats, (word, cats))

    def test_pinned_200_has_possessive_have_and_interposed_time_pp(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertIn("I had not at that time the honour", cases[200]["text"])
        prepared, _, result = parse_corpus_case(
            make_parser(), cases[200], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        nodes = list(self.nodes(best))
        predicate = [n for n in nodes if n.rule_id == "vp_have_neg_pp_object"]
        self.assertTrue(predicate)
        self.assertEqual([c.category for c in predicate[0].children],
                         ["HAVE", "NEG", "PP", "NP"])
        text = prepared.analysis_text
        self.assertEqual(text[predicate[0].children[2].start:
                              predicate[0].children[2].end], "at that time")
        self.assertTrue(text[predicate[0].children[3].start:
                             predicate[0].children[3].end].startswith("the honour"))
        lexical = {(n.category, text[n.start:n.end]) for n in nodes if not n.children}
        self.assertTrue({("DET", "any"), ("PREP", "beyond"),
                         ("PREP", "at"), ("N", "time")} <= lexical)
        self.assertNotIn(("N", "at"), lexical)
        self.assertNotIn(("V", "time"), lexical)



class TemporalBeforeCompoundTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from TemporalBeforeCompoundTests.nodes(child)

    def test_before_clausal_and_prepositional_readings_coexist(self):
        parser = make_parser()
        for text in ("Mary left before John arrived.",
                     "Before John arrived, Mary left."):
            report = parser.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, report.result.stats)
            self.assertTrue(any(n.category == "CONJ"
                                and text[n.start:n.end].casefold() == "before"
                                for n in self.nodes(best)))
        cats = {c.category for c in parser.parse("before").lattice.candidates}
        self.assertTrue({"CONJ", "PREP", "ADV"} <= cats, cats)

    def test_tete_a_tete_is_one_nominal_span_without_consuming_dash(self):
        parser = make_parser()
        text = "the tete-a-tete--was over"
        lattice = parser.parse(text).lattice
        candidates = [c for c in lattice.candidates
                      if c.surface == "tete-a-tete" and c.category == "N"]
        self.assertTrue(candidates)
        self.assertTrue(all(text[c.span_start:c.span_end] == "tete-a-tete"
                            for c in candidates))
        self.assertTrue(any(c.surface == "--" and c.category == "DASH"
                            for c in lattice.candidates))

    def test_pinned_239_keeps_temporal_clause_and_compound_noun(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[239]["text"].startswith("Yet time and her aunt"))
        prepared, _, result = parse_corpus_case(
            make_parser(), cases[239], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        nodes = list(self.nodes(best))
        spans = {(n.category, text[n.start:n.end]) for n in nodes}
        self.assertTrue({("CONJ", "before"), ("N", "tete-a-tete"),
                         ("CLAUSE", "the tete-a-tete was over"),
                         ("NP", "her patience and her ideas")} <= spans, spans)
        self.assertIn("clause_sub", {n.rule_id for n in nodes})
        self.assertIn("clause_comma_coord", {n.rule_id for n in nodes})
        self.assertFalse(any(n.category == "DET" and
                            n.start > text.index("tete-a-tete")
                            for n in nodes))


class PluralGenitivePassiveControlTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from PluralGenitivePassiveControlTests.nodes(child)

    def test_plural_genitive_preserves_ascii_and_curly_apostrophe_spans(self):
        from seman_parser.segmentation import tokenize
        parser = make_parser()
        for mark in ("'", "’"):
            text = "She had a few minutes" + mark + " conversation."
            tokens = tokenize(text)
            report = parser.parse(text)
            self.assertEqual(report.lattice.tokens, tokens)
            clitics = [c for c in report.lattice.candidates
                       if c.source == "plural-genitive-apostrophe"]
            self.assertEqual(len(clitics), 1)
            self.assertEqual(text[clitics[0].span_start:clitics[0].span_end], mark)
            self.assertEqual(clitics[0].features.as_dict()["genitive_clitic"], "true")
            best = report.result.best()
            self.assertIsNotNone(best, report.result.stats)
            self.assertIn("np_genitive", {n.rule_id for n in self.nodes(best)})
        for text in ("the dog' bowl", "a few minutes conversation", "John's coat"):
            self.assertFalse(any(c.source == "plural-genitive-apostrophe"
                                 for c in parser.parse(text).lattice.candidates), text)

    def test_passive_control_licenses_adverbs_and_rejects_wrong_morphology(self):
        parser = make_parser()
        for text, rule in (
            ("She was scarcely ever prevailed upon to leave.",
             "vp_passive_control_interposed_advp"),
            ("He was kindly persuaded to stay.",
             "vp_passive_control_interposed_adv"),
        ):
            report = parser.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, report.result.stats)
            self.assertIn(rule, {n.rule_id for n in self.nodes(best)})
        forbidden = {"vp_passive_control_interposed_adv",
                     "vp_passive_control_interposed_advp"}
        for text in ("She were scarcely ever prevailed upon to leave.",
                     "She was scarcely ever prevail upon to leave.",
                     "She was scarcely ever slept to leave."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertFalse(forbidden & {n.rule_id for n in self.nodes(tree)}, text)

    def test_pinned_232_has_genitive_adverb_and_passive_control(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[232]["text"].startswith("She not unfrequently"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[232], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        nodes = list(self.nodes(best))
        spans = {(n.category, text[n.start:n.end]) for n in nodes}
        self.assertTrue({("ADV", "unfrequently"), ("POSS", "'"),
                         ("NP", "a few minutes' conversation"),
                         ("ADVP", "scarcely ever"), ("V", "prevailed upon"),
                         ("VP-NP", "get out")} <= spans, spans)
        self.assertIn("vp_passive_control_interposed_advp",
                      {n.rule_id for n in nodes})
        self.assertIn("np_genitive", {n.rule_id for n in nodes})




class ExactNominalFocusTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from ExactNominalFocusTests.nodes(child)

    def test_exactly_focus_uses_existing_nominal_rule(self):
        parser = make_parser()
        for text in ("He should copy exactly what he had before him.",
                     "He copied exactly the instructions."):
            report = parser.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, report.result.stats)
            focused = [n for n in self.nodes(best) if n.rule_id == "np_adv_np"]
            self.assertTrue(focused, text)
            self.assertTrue(any(text[n.start:n.end].startswith("exactly ") for n in focused))
        for word in ("exactly", "quickly"):
            report = parser.parse("He copied " + word + " the instructions.")
            marked = [c for c in report.lattice.candidates if c.surface == word
                      and c.features.as_dict().get("nominal_modifier") == "true"]
            self.assertEqual(bool(marked), word == "exactly")
        self.assertIsNotNone(parser.parse("He copied the instructions exactly.").result.best())

    def test_pinned_112_exactly_modifies_free_relative(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[112]["text"].startswith("Our instructions to Mr. Dick"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[112], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        nodes = list(self.nodes(best))
        text = prepared.analysis_text
        relatives = [n for n in nodes if n.rule_id == "np_nominal_free_relative_object_pp"
                     and text[n.start:n.end] == "what he had before him"]
        self.assertTrue(relatives)
        self.assertTrue(any(n.rule_id == "np_adv_np"
                            and text[n.start:n.end].startswith("exactly what he had before him")
                            for n in nodes))
        self.assertTrue(any(n.rule_id == "vp_modal_bare"
                            and text[n.start:n.end].startswith("should copy exactly")
                            for n in nodes))


class IntransitiveDepictivePurposeTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from IntransitiveDepictivePurposeTests.nodes(child)

    def test_depictive_and_purpose_constructions_are_licensed(self):
        parser = make_parser()
        for text, rule in (
            ("She returned from work tired.", "vp_intransitive_pp_depictive"),
            ("They retired to meditate.", "vp_intransitive_purpose_infinitive"),
        ):
            result = parser.parse(text).result
            best = result.best()
            self.assertIsNotNone(best, result.stats)
            self.assertIn(rule, {n.rule_id for n in self.nodes(best)})
        control = parser.parse("Lena decided to read the novel.").result.best()
        self.assertIsNotNone(control)
        self.assertIn("vp_to_inf", {n.rule_id for n in self.nodes(control)})
        forbidden = {"vp_intransitive_pp_depictive", "vp_intransitive_purpose_infinitive"}
        for text in ("He returns from work tired.", "He returns to meditate."):
            self.assertIsNotNone(parser.parse(text).result.best(), text)
        for text in ("They returns from work tired.", "They returns to meditate.",
                     "He required to meditate.", "He required from work tired."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertFalse(forbidden & {n.rule_id for n in self.nodes(tree)}, text)

    def test_pinned_340_coordinates_depictive_action_and_purpose(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[340]["text"].startswith("I broke from the house"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[340], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        nodes = list(self.nodes(best))
        spans = {(n.rule_id, text[n.start:n.end]) for n in nodes}
        self.assertIn(("vp_intransitive_pp_depictive",
                       "broke from the house angry and disturbed"), spans)
        self.assertIn(("adjp_coord", "angry and disturbed"), spans)
        self.assertIn(("vp_intransitive_purpose_infinitive",
                       "retired to meditate on some other mode of action"), spans)
        self.assertIn("vp_coord_finite", {n.rule_id for n in nodes})


class DegreeNominalAdjectiveGapTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from DegreeNominalAdjectiveGapTests.nodes(child)

    def test_degree_nominal_gap_licenses_only_selected_preposition(self):
        parser = make_parser()
        for text in ("It is too great a violation for him to be guilty of.",
                     "It is too great a violation, for him to be guilty of."):
            result = parser.parse(text).result
            best = result.best()
            self.assertIsNotNone(best, result.stats)
            self.assertIn("vp_infinitival_adjective_selected_pp_gap",
                          {n.rule_id for n in self.nodes(best)})
        for text in ("It is too great a violation for him to be guilty with.",
                     "It is too great a violation for him to is guilty of.",
                     "It is too great a violation for him to be happy of."):
            self.assertIsNone(parser.parse(text).result.best(), text)
        self.assertIsNone(parser.parse("He is guilty of.").result.best())
        self.assertIsNotNone(parser.parse("He is guilty of it.").result.best())
        result = parser.parse("It was really too great a mistake.").result
        self.assertIn("vp_copular_adverb_nominal_predicate",
                      {n.rule_id for n in self.nodes(result.best())})

    def test_pinned_209_keeps_degree_antecedent_and_list_inside_of(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[209]["text"].startswith("It is really too great"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[209], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        nodes = list(self.nodes(best))
        relative = next(n for n in nodes
                        if n.rule_id == "np_for_infinitival_adjective_pp_relative_comma")
        self.assertEqual(text[relative.children[0].start:relative.children[0].end],
                         "too great a violation of decency, honour, and interest")
        self.assertEqual(text[relative.children[3].start:relative.children[3].end], "him")
        self.assertTrue(any(n.category == "PP" and
                            text[n.start:n.end] == "of decency, honour, and interest"
                            for n in nodes))
        self.assertTrue(any(n.rule_id == "vp_infinitival_adjective_selected_pp_gap"
                            and text[n.start:n.end] == "be guilty of" for n in nodes))
        self.assertIn("vp_copular_adverb_nominal_predicate", {n.rule_id for n in nodes})


class EquativeInciseBeforePPTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from EquativeInciseBeforePPTests.nodes(child)

    def test_equative_incise_requires_paired_commas_and_as_markers(self):
        parser = make_parser()
        text = "She walked, as slowly as she could, to the house."
        best = parser.parse(text).result.best()
        self.assertIsNotNone(best)
        self.assertIn("pp_equative_incise", {n.rule_id for n in self.nodes(best)})
        for text in ("She walked, than slowly as she could, to the house.",
                     "She walked, as slowly than she could, to the house.",
                     "She walked as slowly as she could, to the house.",
                     "She walked, as slowly as she could to the house."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn("pp_equative_incise",
                                 {n.rule_id for n in self.nodes(tree)}, text)

    def test_pinned_441_keeps_particle_comparison_and_destination(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[441]["text"].startswith("In the meantime the supervisor"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[441], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        nodes = list(self.nodes(best))
        text = prepared.analysis_text
        vp = next(n for n in nodes if n.rule_id == "pp_equative_incise")
        self.assertEqual([text[n.start:n.end] for n in vp.children],
                         [",", "as fast as he could,", "to Kitt's Hole"])
        spans = {(n.category, text[n.start:n.end]) for n in nodes}
        self.assertTrue({("PARTICLE", "on"), ("ADV", "fast"),
                         ("PROPER-NOUN", "Kitt"), ("POSS", "'s")} <= spans)
        self.assertIn("clause_modal_ellipsis", {n.rule_id for n in nodes})
        self.assertTrue(any(n.rule_id == "vp_particle" and text[n.start:n.end] == "rode on" for n in nodes))


class DistributivePossessionQuotedNameTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from DistributivePossessionQuotedNameTests.nodes(child)

    def test_distributive_group_and_quoted_nominal_contrasts(self):
        parser = make_parser()
        for text in ("They had each of them several names.",
                     "We have each of us a room."):
            best = parser.parse(text).result.best()
            self.assertIsNotNone(best)
            self.assertIn("vp_have_distributive_object", {n.rule_id for n in self.nodes(best)})
        for text in ("They had each of him several names.",
                     "They have each with them several names."):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vp_have_distributive_object",
                                 {n.rule_id for n in self.nodes(tree)})
        for text in ("The name was 'father'.", "The name was 'father.'"):
            best = parser.parse(text).result.best()
            self.assertIsNotNone(best)
            self.assertTrue(any(n.features.as_dict().get("quoted_nominal") == "true"
                                for n in self.nodes(best)))

    def test_pinned_357_preserves_distribution_object_and_quoted_name(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[357]["text"].startswith("The youth and his companion"))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[357], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        nodes = list(self.nodes(best))
        vp = next(n for n in nodes if n.rule_id == "vp_have_distributive_object")
        self.assertEqual([text[n.start:n.end] for n in vp.children],
                         ["had", "each of them", "several names"])
        self.assertTrue(any(n.rule_id == "wh_supplementary_subject_comma"
                            and text[n.start:n.end] == ", which was 'father.'"
                            for n in nodes))
        quoted = next(n for n in nodes if n.rule_id == "dialogue_quoted_nominal_terminal")
        self.assertEqual(text[quoted.start:quoted.end], "'father.'")
        self.assertEqual([n.category for n in quoted.children],
                         ["OPEN-QUOTE", "N", "COMMA", "CLOSE-QUOTE"])
if __name__ == "__main__":
    unittest.main()


    def test_english_placeholder_and_dash_have_independent_lexical_spans(self):
        p = make_parser()
        quote = "Old what’s-his-name’s in a bad way."
        result = p.parse(quote)
        self.assertTrue(result.result.completed, result.result.stats)
        units = [
            candidate for candidate in result.lattice.candidates
            if candidate.source == "lexicalized-placeholder-name"
        ]
        self.assertEqual([x.surface for x in units], ["what’s-his-name"])
        # The trailing 's is a distinct copular clitic, not part of the
        # lexical nominal that denotes an unnamed person.
        self.assertTrue(any(
            c.category == "COPULA" and c.span_start >= units[0].span_end
            for c in result.lattice.candidates
        ))

        literary = "And the stage-cutch that'll take you to--wherever it is."
        lattice = p.parse(literary).lattice
        self.assertIn(
            ("stage-cutch", "N"),
            {(c.surface, c.category) for c in lattice.candidates}
        )
        self.assertTrue({
            ("--", "DASH"), ("--", "COMMA"),
        } <= {(c.surface, c.category) for c in lattice.candidates})

    def test_handkerchiefs_wordnet_plural_is_not_missing(self):
        p = make_parser()
        lattice = p.parse(
            "I could hardly see the family for the handkerchiefs they waved."
        ).lattice
        readings = [
            c for c in lattice.candidates
            if c.surface.casefold() == "handkerchiefs" and c.category == "N"
        ]
        self.assertTrue(readings)
        self.assertTrue(any(
            c.lemma == "handkerchief"
            and c.features.as_dict().get("number") == "plural"
            for c in readings
        ))


class NominalComparisonParenthesisTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from NominalComparisonParenthesisTests.nodes(child)

    def test_like_readings_and_delimited_comparison(self):
        parser = make_parser()
        categories = {c.category for c in parser.parse('like').lattice.candidates}
        self.assertTrue({'PREP', 'V', 'ADJ'} <= categories)
        text = 'She walked, like a racer, to the house.'
        best = parser.parse(text).result.best()
        self.assertIsNotNone(best)
        self.assertIn('comparison_pp_tail', {n.rule_id for n in self.nodes(best)})
        for text in ('She walked, like a racer to the house.',
                     'She walked like a racer, to the house.',
                     'She walked, with a racer, to the house.'):
            for tree in parser.parse(text).result.alternatives(limit=8):
                self.assertNotIn('comparison_pp_tail', {n.rule_id for n in self.nodes(tree)})
        lattice = parser.parse('set').lattice
        self.assertTrue({'base', 'finite', 'ed'} <= {
            c.features.as_dict().get('vform') for c in lattice.candidates if c.category == 'V'})

    def test_pinned_467_preserves_perfect_passive_and_adverb_attachment(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[467]['text'].startswith('Every thought of his soul'))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[467], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        nodes = list(self.nodes(best))
        text = prepared.analysis_text
        perfect = next(n for n in nodes if n.rule_id == 'vp_perfect_passive')
        self.assertEqual([text[n.start:n.end] for n in perfect.children], ['had', 'been', 'set'])
        self.assertEqual(perfect.features.as_dict()['voice'], 'passive')
        adverb = next(n for n in nodes if n.rule_id == 'vp_adv')
        self.assertEqual([text[n.start:n.end] for n in adverb.children], ['had been set', 'full-stretch'])
        incise = next(n for n in nodes if n.rule_id == 'pp_equative_incise')
        self.assertEqual([text[n.start:n.end] for n in incise.children], [',', 'like a racer,', 'on that money'])
        tail = next(n for n in nodes if n.rule_id == 'comparison_pp_tail')
        self.assertEqual([text[n.start:n.end] for n in tail.children], ['like', 'a racer', ','])
        self.assertTrue(any(n.category == 'NP' and text[n.start:n.end] == 'Every thought of his soul' for n in nodes))



class TitledIndependentGenitiveTests(unittest.TestCase):
    @staticmethod
    def nodes(node):
        yield node
        for child in node.children:
            yield from TitledIndependentGenitiveTests.nodes(child)

    def test_titled_genitive_requires_suffix_and_keeps_abbreviation_span(self):
        parser = make_parser()
        np = Parser(parser.resources, goal_category='NP')
        for text in ("St. Clement's", "Saint Paul's", "Sir William's"):
            best = np.parse(text).result.best()
            self.assertIsNotNone(best, text)
            self.assertEqual(best.rule_id, 'np_titled_independent_genitive', text)
            self.assertEqual(best.children[-1].features.as_dict()['genitive_clitic'], 'true')
            if text.startswith('St.'):
                title = best.children[0]
                self.assertEqual((title.category, text[title.start:title.end]), ('TITLE', 'St.'))
        for text in ('St. Clement', 'Saint Paul his', "'s", 'Sir his'):
            for tree in np.parse(text).result.alternatives(limit=8):
                self.assertNotIn('np_titled_independent_genitive', {n.rule_id for n in self.nodes(tree)})
        best = np.parse("Wickham's lodgings").result.best()
        self.assertIsNotNone(best)
        self.assertNotIn('np_titled_independent_genitive', {n.rule_id for n in self.nodes(best)})

    def test_in_that_parish_is_compositional_location_not_adverb_plus_noun(self):
        parser = make_parser()
        text = 'They were in that parish.'
        best = parser.parse(text).result.best()
        self.assertIsNotNone(best)
        nodes = list(self.nodes(best))
        self.assertTrue(any(n.category == 'PP' and text[n.start:n.end] == 'in that parish' for n in nodes))
        self.assertTrue(any(n.category == 'DET' and text[n.start:n.end] == 'that' for n in nodes))
        readings = parser.parse('in that').lattice.candidates
        self.assertTrue(any(c.surface == 'in that' and c.category == 'CONJ' for c in readings))
        self.assertTrue(any(c.surface == 'in that' and c.category == 'ADV' and c.features.as_dict().get('nominal_modifier') == 'false' for c in readings))
        self.assertTrue(all(c.features.as_dict().get('nominal_modifier') == 'false' for c in readings if c.surface == 'in that' and c.category == 'ADV'))

    def test_pinned_212_preserves_incise_titled_place_and_causal_location(self):
        from scripts.diagnose_novel_parses import select_cases
        from research.verbnet_lr.corpus_pipeline import parse_corpus_case
        cases, _ = select_cases(500)
        self.assertTrue(cases[212]['text'].startswith('We were married, you know'))
        prepared, lattice, result = parse_corpus_case(
            make_parser(), cases[212], max_items=50000, kbest_work_limit=500000)
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        text = prepared.analysis_text
        nodes = list(self.nodes(best))
        place = next(n for n in nodes if n.rule_id == 'np_titled_independent_genitive')
        self.assertEqual([text[n.start:n.end] for n in place.children], ['St.', 'Clement', "'s"])
        for rule, span in [('vp_passive', 'were married'),
                           ('parenthetical_interpersonal_you_know', ', you know,'),
                           ('np_genitive', "Wickham's lodgings"),
                           ('pp_prep_np', 'in that parish')]:
            self.assertTrue(any(n.rule_id == rule and text[n.start:n.end] == span for n in nodes), (rule, span))
        self.assertTrue(any(n.rule_id == 'clause_comma_sub' for n in nodes))
        self.assertFalse(any(n.category == 'COMMA' and n.start == place.start + 2 for n in nodes))
        self.assertTrue(any(n.category == 'OPEN-QUOTE' for n in nodes))
        self.assertTrue(any(n.category == 'CLOSE-QUOTE' for n in nodes))
