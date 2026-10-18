"""Compare predictor discrimination only among equal-length sentences."""
import unittest
from scripts.audit_structural_prefix_risk import matched_auc,evaluate

class StructuralRiskTests(unittest.TestCase):
    def test_perfectly_separated_at_equal_length(self):
        items=[
            {"tokens":10,"score":1,"bad":False},
            {"tokens":10,"score":3,"bad":True},
            {"tokens":20,"score":1,"bad":False},
            {"tokens":20,"score":5,"bad":True},
        ]
        self.assertEqual(matched_auc(items,"score","bad"),(1.0,2))

    def test_length_confound_is_removed(self):
        items=[
            {"tokens":8,"score":8,"bad":False},
            {"tokens":9,"score":9,"bad":True},
        ]
        self.assertEqual(matched_auc(items,"score","bad"),(None,0))

    def test_identical_scores_are_chance(self):
        items=[
            {"tokens":12,"score":7,"bad":False},
            {"tokens":12,"score":7,"bad":True}
        ]
        self.assertEqual(matched_auc(items,"score","bad"),(.5,1))

if __name__=="__main__":
    unittest.main()
