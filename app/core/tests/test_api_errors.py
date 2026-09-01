from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core.error_views import page_not_found, server_error
from core.exceptions import api_exception_handler
from core.middleware import LegacyApiDeprecationMiddleware


class ApiExceptionHandlerTests(SimpleTestCase):
    def test_converts_django_validation_error_to_json_400(self):
        response = api_exception_handler(
            DjangoValidationError({"name": ["Bắt buộc."]}),
            {"view": object()},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["name"], ["Bắt buộc."])

    def test_converts_integrity_error_to_safe_json_409(self):
        response = api_exception_handler(
            IntegrityError("sensitive database detail"),
            {"view": object()},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "integrity_error")
        self.assertNotIn("sensitive database detail", str(response.data))


class ApiErrorViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_api_404_and_500_are_json(self):
        not_found = page_not_found(
            self.factory.get("/api/v1/missing/"),
            Exception("missing"),
        )
        internal_error = server_error(
            self.factory.get("/api/v1/failing/")
        )

        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(not_found["Content-Type"], "application/json")
        self.assertEqual(internal_error.status_code, 500)
        self.assertEqual(internal_error["Content-Type"], "application/json")


class LegacyApiDeprecationMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = LegacyApiDeprecationMiddleware(
            lambda request: HttpResponse("ok")
        )

    def test_marks_legacy_api_response(self):
        response = self.middleware(
            self.factory.get("/api/quanlyvanhanh/thiet-bi/")
        )

        self.assertEqual(response["Deprecation"], "true")
        self.assertIn("/api/v1/", response["Link"])

    def test_does_not_mark_versioned_api_response(self):
        response = self.middleware(
            self.factory.get("/api/v1/quanlyvanhanh/thiet-bi/")
        )

        self.assertNotIn("Deprecation", response)
