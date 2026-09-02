from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class OrganizationMigrationAuditTests(TestCase):
    def test_audit_passes_for_organization_ownership(self):
        output = StringIO()

        call_command(
            "audit_organization_migration",
            "--fail-on-error",
            stdout=output,
        )

        self.assertIn("Ownership và quyền tổ chức đạt yêu cầu.", output.getvalue())
