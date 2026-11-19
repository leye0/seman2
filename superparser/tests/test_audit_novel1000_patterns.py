from unittest import TestCase

from scripts import audit_novel1000_patterns as audit


def node(rule, span, *, category="NP", children=(), features=None, **anchors):
    return {"rule_id": rule, "span": list(span), "category": category,
            "children": list(children), "features": features or {},
            "syntax": {"anchors": anchors}}


class Novel1000PatternAuditTest(TestCase):
    def test_relative_pp_transmits_the_preposition_not_the_verb(self):
        sea = node("np_det_n", (0, 7), referent="lex:4:7:N:sea")
        gap = node("vp_gap_pp", (13, 22), features={"gap": "pp"},
                   event="lex:13:19:V:sail", prep="lex:20:22:PREP:on")
        relative = node("wh_bare", (8, 22), children=[gap])
        root = node("np_relative_obj", (0, 22), children=[sea, relative])
        result = audit.relative(root, [("AFFECTED", [13, 19], [4, 7])])
        self.assertEqual(result["variant"], "pp")
        self.assertEqual(result["owner"]["span"], [20, 22])
        self.assertEqual(result["direct_graph_roles"], [])

    def test_perfect_object_uses_the_lexical_predicate_and_exact_span(self):
        head = node("np_det_n", (0, 8), referent="lex:4:8:N:book")
        gap = node("vp_gap_perfect_transitive", (12, 20), features={"gap": "object"},
                   event="lex:12:15:HAVE:have", lexical_predicate="lex:16:20:V:read")
        relative = node("wh_bare_perfect_object_relative", (9, 20), children=[gap])
        root = node("np_relative_obj", (0, 20), children=[head, relative])
        graph = [("WRONG_AUX", [12, 15], [4, 8]), ("WRONG_SPAN", [16, 20], [0, 8]),
                 ("THEME", [16, 20], [4, 8])]
        result = audit.relative(root, graph)
        self.assertEqual(result["direct_graph_roles"], ["THEME"])
        self.assertIsNone(audit.anchor(gap, "missing"))
        self.assertIsNone(audit.anchor(head, "event"))

    def test_coordination_requires_direct_finite_vp_pair_and_overt_subject(self):
        subject = "lex:0:2:PRONOUN:he"
        np = node("np_indef_pron", (0, 2), referent=subject)
        vp = node("vp_coord_finite", (3, 21), category="VP", features={"vform": "finite"},
                  left="lex:3:9:V:change", right="lex:15:21:V:depart")
        cl = node("clause_np_vp", (0, 21), category="CLAUSE", children=[np, vp],
                  subject=subject)
        graph = [("AGENT", [3, 9], [0, 2]), ("CONJUNCT", [3, 9], [15, 21])]
        result = audit.finite_pair(cl, graph)
        self.assertEqual(result["first_graph_roles"], ["AGENT"])
        self.assertEqual(result["second_graph_roles"], [])
        vp["features"]["vform"] = "base"
        self.assertIsNone(audit.finite_pair(cl, graph))
        vp["features"]["vform"] = "finite"
        vp["category"] = "CLAUSE"
        self.assertIsNone(audit.finite_pair(cl, graph))

    def test_report_needs_source_governors_and_keeps_them_separate_from_graph(self):
        def item(ident, kind, start, end, *, governor=None, relation=None):
            return dict(id=ident, function=kind, start=start, end=end,
                        governor=governor, relation=relation, evidence="typed_source")

        turn = item("t0", "split_direct_speech_turn", 0, 30)
        report = item("r0", "reporting_clause", 8, 15, governor="t0",
                      relation="intercalated_speech_tag")
        first = item("q0", "direct_speech", 0, 7, governor="r0", relation="reported_content")
        second = item("q1", "direct_speech", 16, 30, governor="q0",
                      relation="resumption_of_split_speech")
        parts = [turn, report, first, second]
        edges = [("REPORTED_CONTENT", [9, 13], [1, 4]),
                 ("CONTROLLED_COMPLEMENT", [1, 4], [17, 20]),
                 ("CONTINUED_SPEECH", [1, 4], [17, 31])]
        result, = audit.split_turns(parts, edges)
        self.assertEqual([e["relation"] for e in result["first_to_second"]],
                         ["CONTROLLED_COMPLEMENT"])
        self.assertEqual(result["report_to_first"][0]["source_span"], [9, 13])
        second["governor"] = "r1"
        self.assertEqual(list(audit.split_turns(parts, edges)), [])

    def test_counts_distinguish_passages_and_hits(self):
        def witness(ident, book):
            return dict(transfer_id=ident, book_id=book, family="relative", variant="subject")

        row, = audit.summarize([witness("Q3-1", 84), witness("Q3-1", 84),
                                witness("Q3-2", audit.TRANSFER_BOOK)])
        self.assertEqual((row["hits"], row["passages"]), (3, 2))
        self.assertEqual((row["discovery_hits"], row["cross_book_hits"]), (2, 1))
