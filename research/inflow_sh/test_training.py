import unittest
from datetime import datetime
import numpy as np
from .train import fit,parity_check,before_fit,metrics


class TrainingTests(unittest.TestCase):
    def test_preprocessing_uses_train_only_and_portable_parity(self):
        rows=[{"features":{"x":x,"z":None},"target_qve":2*x+1} for x in [1.,2.,3.,4.]]
        model,ridge,scaler=fit(rows,["x","z"],1)
        validation=[{"features":{"x":None,"z":1000000},"target_qve":0},{"features":{"x":10000,"z":None},"target_qve":0}]
        self.assertEqual(model["impute"],[2.5,0.])
        self.assertEqual(model["center"],[2.5,0.])
        self.assertLess(parity_check(model,validation,ridge,scaler),1e-8)

    def test_training_excludes_labels_unknown_at_fit_time(self):
        rows=[{"target_assumed_known_at":"2025-01-01T07:00:00+07:00"},{"target_assumed_known_at":"2025-01-02T07:00:00+07:00"}]
        self.assertEqual(len(before_fit(rows,datetime.fromisoformat("2025-01-01T07:30:00+07:00"))),1)

    def test_metrics_empty_and_constant_nse(self):
        self.assertEqual(metrics([],[]),{"n":0})
        self.assertIsNone(metrics([1,1],[1,1])["nse"])
        self.assertEqual(metrics([400],[300])["high_day_mean_underforecast"],100)
