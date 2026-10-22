from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from thongsothuyvan.vrain_views import _vrain_error_response


class VrainErrorsTests(SimpleTestCase):
    def test_technical_errors_are_logged_not_returned(self):
        for error, status in [
            (requests.ConnectionError("DNS internal-host secret"), 503),
            (requests.Timeout("internal timeout"), 503),
            (requests.HTTPError("upstream private details"), 502),
            (RuntimeError("private details"), 500),
        ]:
            with self.subTest(error=error), patch(
                "thongsothuyvan.vrain_views.logger.warning"
            ) as log:
                response = _vrain_error_response(error)
                self.assertEqual(response.status_code, status)
                self.assertFalse(response.data["ok"])
                self.assertNotIn(str(error), response.data["error"])
                log.assert_called_once()
