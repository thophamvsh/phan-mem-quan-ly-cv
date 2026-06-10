from django.test import SimpleTestCase

from quanlyvanhanh.configs.operation_configs import (
    get_dien_factory_config,
    get_tomay_device_suffix,
    get_tram_factory_config,
)


class OperationConfigsTests(SimpleTestCase):
    def test_dien_config_clones_song_hinh_layout_for_new_factory(self):
        config = get_dien_factory_config("TKT")
        device_codes = [group["device_code"] for group in config["layout"]]

        self.assertEqual(device_codes[:3], ["TKT.TB.H1", "TKT.TB.H2", "TKT.TB.TPP"])
        self.assertIn("TKT", config["title"])
        self.assertEqual(sum(len(group["columns"]) for group in config["layout"]), 33)

    def test_dien_config_returns_deep_copy(self):
        first_config = get_dien_factory_config("SH")
        first_config["layout"][0]["device_code"] = "BROKEN"

        second_config = get_dien_factory_config("SH")

        self.assertEqual(second_config["layout"][0]["device_code"], "SH.TB.H1")

    def test_tram_config_clones_song_hinh_devices_for_new_factory(self):
        config = get_tram_factory_config("TKT")
        device_codes = [column["ma_thiet_bi"] for column in config["columns"]]

        self.assertEqual(len(device_codes), 18)
        self.assertTrue(all(code.startswith("TKT.TB.") for code in device_codes))
        self.assertEqual(device_codes[0], "TKT.TB.TPP.110.T1")

    def test_tomay_suffix_uses_factory_specific_rules(self):
        self.assertEqual(get_tomay_device_suffix("SH", "toc_do", "H2"), ".GOV.TB3")
        self.assertEqual(get_tomay_device_suffix("TKT", "toc_do", "H2"), ".GOV.TB3")
        self.assertEqual(get_tomay_device_suffix("VS", "toc_do", "H1"), ".GOV")
        self.assertEqual(get_tomay_device_suffix("VS", "toc_do", "H2"), ".GOV(new)")
