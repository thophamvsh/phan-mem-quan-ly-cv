import copy,json,unittest
from datetime import date,datetime,timedelta
from thongsothuyvan.inflow_forecasting import (RAIN_FIELDS,VN,FEATURE_VERSION,build_dataset,features_at,digest,predict_artifact,prepare_sources,experimental_prediction)


def source_fixture():
    start=date(2024,1,1)
    return {"schema_version":"sh-source-v1","plant":"songhinh","hydrology":[{"id":i+1,"ngay":str(start+timedelta(days=i)),"qve":100+i} for i in range(30)],
            "production":[{"id":i+101,"thoi_gian":str(start+timedelta(days=i))+"T00:00:00+07:00","cot_j":10+i,"cot_i":999999} for i in range(30)],
            "rain":[{"id":i+201,"Thoi_gian":str(start+timedelta(days=i))+"T00:00:00+07:00","sync_status":"unknown",**{name:i for name in RAIN_FIELDS}} for i in range(30)]}


class InflowForecastingTests(unittest.TestCase):
    def test_future_values_do_not_change_features_or_source_ids(self):
        source=source_fixture();issue=datetime(2024,1,20,7,30,tzinfo=VN)
        before=features_at(source,issue)
        altered=copy.deepcopy(source)
        for row in altered["hydrology"]:
            if row["ngay"]>="2024-01-20":row["qve"]=999999
        for row in altered["rain"]:
            if row["Thoi_gian"]>="2024-01-20":
                for name in RAIN_FIELDS:row[name]=999999
        for row in altered["production"]:
            if row["thoi_gian"]>="2024-01-20":row["cot_j"]=999999
        self.assertEqual(before,features_at(altered,issue))
        self.assertEqual(before["assumed_cutoff_day"],"2024-01-19")

    def test_target_day_and_label_source_are_correct(self):
        rows,_=build_dataset(source_fixture())
        row=next(r for r in rows if r["target_day"]=="2024-01-21")
        self.assertTrue(row["issue_time"].startswith("2024-01-20T07:30"))
        self.assertEqual(row["target_qve"],120)
        self.assertEqual(row["features"]["qve_latest"],118)
        self.assertEqual(row["features"]["qcm_lag_0"],28)
        self.assertTrue(row["target_assumed_known_at"].startswith("2024-01-22T07:00"))

    def test_missing_calendar_day_is_not_previous_row_or_zero(self):
        source=source_fixture();source["hydrology"]=[r for r in source["hydrology"] if r["ngay"]!="2024-01-18"]
        row=features_at(source,datetime(2024,1,20,7,30,tzinfo=VN))
        self.assertIsNone(row["features"]["qve_lag_1"])
        self.assertIsNone(row["features"]["qve_mean3"])
        self.assertEqual(row["features"]["qve_lag_1_missing"],1)

    def test_availability_delay_and_pre_publication_cutoff(self):
        source=source_fixture()
        for issue,lag in [(datetime(2024,1,20,6,59,tzinfo=VN),1),(datetime(2024,1,20,7,30,tzinfo=VN),2)]:
            self.assertEqual(features_at(source,issue,lag)["assumed_cutoff_day"],"2024-01-18")
        with self.assertRaises(ValueError):features_at(source,datetime(2024,1,20))

    def test_duplicate_rain_is_excluded_and_partial_sum_not_complete(self):
        source=source_fixture();source["rain"].append(copy.deepcopy(source["rain"][18]))
        row=features_at(source,datetime(2024,1,20,7,30,tzinfo=VN))
        self.assertIsNone(row["features"]["rain_Dap_Tran_last"])
        self.assertIsNone(row["features"]["rain_Dap_Tran_sum3"])
        self.assertAlmostEqual(row["features"]["rain_Dap_Tran_coverage3"],2/3)
        self.assertEqual(prepare_sources(source)[3]["rain"],["2024-01-19"])

    def test_stale_history_returns_unavailable(self):
        self.assertIsNone(features_at(source_fixture(),datetime(2024,2,5,7,30,tzinfo=VN)))

    def test_portable_artifact_checks_checksum_missing_and_schema(self):
        model={"schema_version":"sh-ridge-json-v1","feature_version":FEATURE_VERSION,"features":["x"],"impute":[3.],"center":[1.],"scale":[2.],"coefficients":[4.],"intercept":1.}
        model["checksum"]=digest(model)
        self.assertEqual(predict_artifact(json.loads(json.dumps(model)),{"x":None}),5)
        self.assertEqual(predict_artifact(model,{"x":-10}),0)
        with self.assertRaises(ValueError):predict_artifact(model,{})
        tampered=copy.deepcopy(model);tampered["intercept"]=9
        with self.assertRaises(ValueError):predict_artifact(tampered,{"x":3})

    def test_utc_timestamps_map_to_vietnam_day(self):
        source=source_fixture();source["production"][0]["thoi_gian"]="2023-12-31T17:00:00Z"
        self.assertIn(date(2024,1,1),prepare_sources(source)[1])

    def test_unqualified_candidate_uses_preselected_baseline(self):
        model={"fallback_baseline":"B0_persistence"};model["checksum"]=digest(model)
        row={"baseline_persistence":17,"baseline_mean3":20}
        result=experimental_prediction(model,row)
        self.assertEqual(result["model"],"B0_persistence")
        self.assertEqual(result["qve_m3s"],17)
        self.assertEqual(result["status"],"experimental_baseline_only")
        self.assertIsNone(experimental_prediction(model,None)["qve_m3s"])
