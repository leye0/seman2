"""Regression controls for the identical-corpus two-pass measurement."""
from __future__ import annotations

import unittest

from scripts.benchmark_snap_two_passes import percentile, timing, tree_shape, syntax_shape
from tests.test_verbnet_lr_full_structure_snap import FullStructureSnapTests


class TwoPassMetricsTests(unittest.TestCase):
    def test_percentile_interpolation(self):
        self.assertEqual(percentile([1,2,3,4,5],.5),3.0)
        self.assertEqual(percentile([1,2,3,4,5],.75),4.0)
        self.assertEqual(percentile([1,2,3,4,5],.90),4.6)
        self.assertIsNone(percentile([],.5))
        self.assertEqual(timing([1,2,3,4,5])["p90_ms"],4.6)

    def test_same_lattice_replays_both_original_attachment_templates(self):
        helper=FullStructureSnapTests(methodName="test_one_type_sequence_snaps_to_both_complete_trees")
        helper.setUp()
        rows=[("PRON",None,1),("V",None,1),
              ("N","sg",1),("PREP",None,1),("N","sg",1)]
        lattice=helper.lattice(["I","saw","girl","with","hat"],[[x] for x in rows])
        first,second=helper.two_attached_trees(lattice)
        idx_a=helper.index.observe(first,lattice=lattice)
        idx_b=helper.index.observe(second,lattice=lattice)
        replay=helper.index.match(lattice)
        self.assertTrue(replay.complete)
        self.assertEqual({m.template_id for m in replay.matches},{idx_a,idx_b})
        self.assertEqual({str(tree_shape(m.item)) for m in replay.matches},
                         {str(tree_shape(first)),str(tree_shape(second))})
        self.assertEqual({str(syntax_shape(m.item)) for m in replay.matches},
                         {str(syntax_shape(first)),str(syntax_shape(second))})


if __name__ == "__main__":
    unittest.main()
