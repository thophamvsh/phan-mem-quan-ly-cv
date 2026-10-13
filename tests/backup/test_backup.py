import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "backup"
sys.path.insert(0, str(SCRIPTS))
import backup_daily as backup
import verify_backup as verify


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_mount_stops_before_writes(self):
        with patch.object(Path, "is_mount", return_value=False):
            with self.assertRaisesRegex(backup.BackupError, "not mounted"):
                backup.check_mount({"mount": "/mnt/nvme"})

    def test_wrong_uuid_rejected(self):
        with patch.object(Path, "is_mount", return_value=True), patch.object(backup, "run", return_value="wrong"):
            with self.assertRaisesRegex(backup.BackupError, "UUID"):
                backup.check_mount({"mount": "/mnt/nvme", "mount_uuid": "expected"})

    def test_insufficient_space(self):
        with patch.object(backup.shutil, "disk_usage") as usage:
            usage.return_value.free = 10
            with self.assertRaises(backup.BackupError):
                backup.require_space(self.root, 11)

    def test_media_archive_detects_changes(self):
        source = self.root / "media"
        source.mkdir()
        (source / "photo.txt").write_text("hello")
        with patch.object(backup, "tree_signature", side_effect=[{}, {"changed": 1}] * 3):
            with self.assertRaisesRegex(backup.BackupError, "changing"):
                backup.archive_tree(source, self.root / "media.tar.gz")

    def test_changing_logs_are_explicit_warning(self):
        source = self.root / "logs"
        source.mkdir()
        with patch.object(backup, "tree_signature", side_effect=[{}, {"changed": 1}]):
            self.assertIn("changed", backup.archive_tree(source, self.root / "logs.tar.gz", live_log=True))

    def test_upload_failure_does_not_verify(self):
        with patch.object(backup, "run", side_effect=backup.BackupError("upload")), patch.object(backup, "remote_verify") as check:
            with self.assertRaises(backup.BackupError):
                backup.publish({"rclone_config": "secret.conf"}, self.root / "a.age", "r2:bucket/key")
            check.assert_not_called()

    def test_remote_checksum_mismatch_is_failure(self):
        archive = self.root / "a.age"
        archive.write_bytes(b"original")
        (self.root / "download-verification.age").write_bytes(b"bad download")
        with patch.object(backup, "run"):
            with self.assertRaisesRegex(backup.BackupError, "checksum"):
                backup.remote_verify({"rclone_config": "secret.conf"}, archive, "r2:bucket/key")

    def test_successful_remote_verification(self):
        archive = self.root / "a.age"
        archive.write_bytes(b"original")
        (self.root / "download-verification.age").write_bytes(b"original")
        with patch.object(backup, "run"):
            backup.remote_verify({"rclone_config": "secret.conf"}, archive, "r2:bucket/key")
        self.assertFalse((self.root / "download-verification.age").exists())

    def test_cleanup_only_verified_expired_runs(self):
        for suffix, verified, age in [("a" * 12, True, 4), ("b" * 12, False, 4), ("c" * 12, True, 1)]:
            directory = self.root / ("vsh-20261013T000000Z-" + suffix)
            directory.mkdir()
            archive = directory / "backup.tar.gz.age"
            archive.write_bytes(b"encrypted")
            if verified:
                backup.write_json(directory / "verified.json", {"verified_at": 1000000 - age * 86400, "sha256": backup.sha256(archive)})
        backup.cleanup(self.root, now=1000000)
        self.assertEqual(len(list(self.root.iterdir())), 2)
        self.assertTrue((self.root / ("vsh-20261013T000000Z-" + "b" * 12)).exists())

    def test_cleanup_preserves_bad_checksum(self):
        directory = self.root / ("vsh-20261013T000000Z-" + "a" * 12)
        directory.mkdir()
        (directory / "backup.tar.gz.age").write_bytes(b"changed")
        backup.write_json(directory / "verified.json", {"verified_at": 0, "sha256": "wrong"})
        backup.cleanup(self.root, now=1000000)
        self.assertTrue(directory.exists())

    def test_command_error_does_not_leak_secret(self):
        with self.assertRaises(backup.BackupError) as caught:
            backup.run([sys.executable, "-c", "import sys; print('secret-password', file=sys.stderr); sys.exit(1)"])
        self.assertNotIn("secret-password", str(caught.exception))

    def test_safe_extraction_rejects_traversal_and_links(self):
        for index, name in enumerate(("../outside", "/absolute", "C:/outside", "a\\outside", "link")):
            archive = self.root / f"bad{index}.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                item = tarfile.TarInfo(name)
                if name == "link":
                    item.type = tarfile.SYMTYPE
                    item.linkname = "outside"
                output.addfile(item)
            with self.assertRaises(backup.BackupError):
                verify.unpack(archive, self.root / f"extract{index}")

    def test_archive_roundtrip(self):
        source = self.root / "media"
        source.mkdir()
        (source / "photo.txt").write_bytes(b"data")
        archive = self.root / "media.tar.gz"
        backup.archive_tree(source, archive)
        verify.unpack(archive, self.root / "restored")
        self.assertEqual((self.root / "restored/photo.txt").read_bytes(), b"data")

    def prepare_flow(self):
        cfg = {"db_container": "isolated-test", "app_container": "isolated-app", "repo": str(self.root),
               "remote": "r2:bucket/daily/orangepi", "recipient_file": "public.txt",
               "rclone_config": "private.conf", "min_free_gib": "0"}
        for name in ("media", "security_logs", "audit_archives"):
            source = self.root / name
            source.mkdir()
            (source / "example.txt").write_text("sample")
            cfg[name] = str(source)
        config = self.root / "safe.conf"
        config.write_text("safe configuration")
        cfg["config_files"] = str(config)
        stage = self.root / "staging"
        stage.mkdir()
        return cfg, stage

    def fake_run(self, args, *, output=None, input_file=None, **kwargs):
        text = " ".join(args)
        if "{{json .Mounts}}" in text:
            return json.dumps([
                {"Destination": "/vol/web/media", "Source": str(self.root / "media")},
                {"Destination": "/vol/audit-archives", "Source": str(self.root / "audit_archives")},
            ])
        if "pg_database_size" in text:
            return "100"
        if "current_database()" in text:
            return "appdb"
        if "SELECT datname" in text:
            return "appdb\npostgres"
        if output is not None:
            output.write(b"test dump contents")
            return ""
        if args[0] == "age":
            Path(args[args.index("-o") + 1]).write_bytes(b"fake encryption for mocked flow")
        return "test metadata"

    def test_wrong_application_source_rejected(self):
        with patch.object(backup, "run", return_value="[]"):
            with self.assertRaisesRegex(backup.BackupError, "Docker mount"):
                backup.check_source_mounts({"app_container": "app", "media": "/wrong"})

    def test_full_mock_flow_marks_success_after_verification_and_removes_plaintext(self):
        cfg, stage = self.prepare_flow()
        with patch.object(backup, "run", side_effect=self.fake_run), patch.object(backup, "publish") as publish:
            receipt = backup.create_backup(cfg, stage)
        publish.assert_called_once()
        directory = stage / receipt["run_id"]
        self.assertTrue((directory / "backup.tar.gz.age").exists())
        self.assertFalse((directory / "payload").exists())
        self.assertFalse((directory / "backup.tar.gz").exists())
        self.assertEqual(json.loads((stage / "last-success.json").read_text())["sha256"], receipt["sha256"])

    def test_verification_failure_keeps_staging_and_never_marks_success(self):
        cfg, stage = self.prepare_flow()
        with patch.object(backup, "run", side_effect=self.fake_run), patch.object(backup, "publish", side_effect=backup.BackupError("verify failed")):
            with self.assertRaises(backup.BackupError):
                backup.create_backup(cfg, stage)
        self.assertFalse((stage / "last-success.json").exists())
        directory = next(stage.iterdir())
        self.assertTrue((directory / "payload/database.dump").exists())
        self.assertFalse((directory / "verified.json").exists())

    def test_database_failure_never_uploads(self):
        cfg, stage = self.prepare_flow()
        with patch.object(backup, "run", side_effect=backup.BackupError("DB unavailable")), patch.object(backup, "publish") as publish:
            with self.assertRaises(backup.BackupError):
                backup.create_backup(cfg, stage)
        publish.assert_not_called()
        self.assertFalse((stage / "last-success.json").exists())

    def test_manifest_rejects_tampered_file(self):
        payload = self.root / "payload"
        payload.mkdir()
        path = payload / "database.dump"
        path.write_bytes(b"original")
        backup.write_json(payload / "manifest.json", {"sha256": {"database.dump": backup.sha256(path)}})
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(backup.BackupError, "checksum"):
            verify.verify_payload(payload)

    @unittest.skipUnless(sys.platform == "linux", "flock requires Linux")
    def test_concurrent_lock_rejected(self):
        with backup.exclusive_lock(self.root / "lock"):
            with self.assertRaises(backup.BackupError):
                with backup.exclusive_lock(self.root / "lock"):
                    self.fail("Concurrent lock acquired")


if __name__ == "__main__":
    unittest.main()
