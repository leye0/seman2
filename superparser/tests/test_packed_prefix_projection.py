"""Prove shared-prefix edges reconstruct each original rule variant."""
import unittest
from types import SimpleNamespace

from research.verbnet_lr.packed_prefix_projection import build_projection, pack_flat, pack_flat_direct
from seman_parser.grammar import load_grammar_rows
from seman_parser.vector_chart import PartialDerivation


def sym(cat,features=None):
    return {"category":cat,"features":features or {}}


def part(id,rule,dot,start,end,edges):
    return SimpleNamespace(
        partial_id=id,rule_index=rule,dot=dot,start=start,end=end,
        derivations=[PartialDerivation(p,c) for p,c in edges])


class SharedPrefixProjectionTests(unittest.TestCase):
    def setUp(self):
        grammar=load_grammar_rows([
            {"id":"vp_v_np","lhs":sym("VP"),"rhs":[sym("V"),sym("NP")]},
            {"id":"pred_v_np","lhs":sym("CLAUSE"),"rhs":[sym("V"),sym("NP")]},
            {"id":"vp_v_pp","lhs":sym("VP"),"rhs":[sym("V"),sym("PP")]},
            {"id":"finite_v_np","lhs":sym("VP"),"rhs":[sym("V",{"vform":"finite"}),sym("NP")]},
        ])
        self.rules=[SimpleNamespace(rule=rule) for rule in grammar]

    def forest(self,partials):
        return SimpleNamespace(
            compiled=SimpleNamespace(rules=self.rules),
            partials=partials)

    def test_shared_group_preserves_reverse_variant_edge_order(self):
        forest=self.forest([
            part(0,0,1,0,4,[(None,1),(None,2)]),
            part(1,1,1,0,4,[(None,2),(None,1)]),
            part(2,2,1,0,4,[(None,1)]),
            part(3,3,1,0,4,[(None,1)]),
            part(4,0,2,0,9,[(0,7),(0,8)]),
            part(5,1,2,0,9,[(1,8),(1,7)]),
        ])
        projection=build_projection(forest)
        self.assertEqual(projection.group_of[0],projection.group_of[1])
        self.assertEqual(projection.group_of[0],projection.group_of[2])
        self.assertNotEqual(projection.group_of[0],projection.group_of[3])
        self.assertEqual(projection.group_of[4],projection.group_of[5])
        self.assertEqual(projection.reconstruct(4),[(0,7),(0,8)])
        self.assertEqual(projection.reconstruct(5),[(1,8),(1,7)])
        stats=projection.metrics(forest)
        self.assertEqual(stats["partials"],6)
        self.assertEqual(stats["shared_groups"],3)
        self.assertLess(stats["interned_edges"],stats["original_edges"])
        flat=pack_flat(forest)
        direct=pack_flat_direct(forest)
        self.assertEqual(direct.verify(forest),sum(
            len(x.derivations) for x in forest.partials))
        self.assertEqual(direct.group_of,flat.group_of)
        self.assertEqual(direct.variant_edges,flat.variant_edges)
        self.assertEqual(direct.children,flat.children)
        self.assertEqual(direct.prev_groups,flat.prev_groups)
        # array() growth can reserve different capacities in equally valid
        # construction orders. Logical edges and all decoded paths must match.
        self.assertEqual(direct.metrics(forest)["unique_edges"],
                         flat.metrics(forest)["unique_edges"])
        self.assertEqual(direct.metrics(forest)["prefix_groups"],
                         flat.metrics(forest)["prefix_groups"])
        self.assertEqual(flat.reconstruct(4),[(0,7),(0,8)])
        self.assertEqual(flat.reconstruct(5),[(1,8),(1,7)])
        self.assertEqual(flat.verify(forest),sum(len(x.derivations) for x in forest.partials))
        self.assertLess(flat.metrics(forest)["flat_arrays_bytes"],
                        stats["projected_edge_objects_estimated_bytes"])

    def test_segment_boundaries_and_rule_features_are_not_conflated(self):
        forest=self.forest([
            part(0,0,1,0,4,[(None,1)]),
            part(1,1,1,1,4,[(None,1)]),
            part(2,3,1,0,4,[(None,1)]),
            part(3,0,1,0,7,[(None,2)]),
        ])
        view=build_projection(forest)
        self.assertEqual(len(view.groups),4)
        self.assertEqual(pack_flat_direct(forest).metrics(forest)["prefix_groups"],4)
        flat=pack_flat(forest)
        self.assertEqual(flat.metrics(forest)["prefix_groups"],4)

    def test_validation_rejects_invalid_projection_ancestry(self):
        forest=self.forest([
            part(0,0,1,0,4,[(None,1)]),
            part(1,1,2,0,8,[(0,2)]),
        ])
        with self.assertRaises(KeyError):
            build_projection(forest)
        with self.assertRaises(KeyError):
            pack_flat_direct(forest)

    def test_empty_forest_is_supported(self):
        forest=self.forest([])
        view=build_projection(forest)
        self.assertEqual(view.metrics(forest)["shared_groups"],0)
        self.assertEqual(view.metrics(forest)["original_edges"],0)
        self.assertEqual(pack_flat(forest).verify(forest),0)
        self.assertEqual(pack_flat_direct(forest).verify(forest),0)


if __name__=="__main__":
    unittest.main()
