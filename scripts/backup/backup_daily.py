#!/usr/bin/env python3
"""Host-only backup runner. Python 3.10+, Docker, age, rclone; no Django imports."""
import argparse
import configparser
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from zoneinfo import ZoneInfo


class BackupError(Exception):
    pass


def run(args, *, output=None, input_file=None, timeout=7200):
    # Never echo argv, stdout or stderr on failure: these can contain secrets.
    try:
        result = subprocess.run(
            args, stdin=input_file, stdout=output or subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, timeout=timeout,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise BackupError(f"{Path(args[0]).name} failed; inspect locally") from exc
    return result.stdout.decode().strip() if output is None else ""


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def read_config(path):
    parser = configparser.ConfigParser(interpolation=None)
    with path.open(encoding="utf-8") as stream:
        parser.read_file(stream)
    return dict(parser["backup"])


def private_file(path):
    mode = path.lstat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_uid != 0 or mode.st_mode & 0o077:
        raise BackupError("Configuration/credential file must be root-owned mode 600")


def check_mount(cfg):
    mount = Path(cfg["mount"])
    if not mount.is_mount():
        raise BackupError("NVMe is not mounted")
    actual = run(["findmnt", "-n", "-o", "UUID", "--target", str(mount)])
    if actual != cfg["mount_uuid"]:
        raise BackupError("Wrong NVMe UUID")
    stage = Path(cfg["staging"])
    if stage != mount / "vsh-backup-staging" or stage.resolve() != stage:
        raise BackupError("Staging must be the dedicated non-symlink NVMe directory")
    return stage


def require_space(stage, required):
    if shutil.disk_usage(stage).free < required:
        raise BackupError("Insufficient staging disk space; no backups were deleted")


@contextmanager
def exclusive_lock(path):
    import fcntl  # Linux host; pure helpers/tests also run on Windows.
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackupError("Another backup is running") from exc
        yield


def entries(root):
    if root.is_symlink() or not root.is_dir():
        raise BackupError("A required source directory is missing or is a symlink")
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(base) / name
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise BackupError("Source contains symlink or special file; review it first")
            yield path


def tree_signature(root):
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in entries(root) if path.is_file()
    }


def archive_tree(root, destination, live_log=False):
    """Retry unstable media; logs are explicitly a bounded live copy, not a snapshot."""
    for attempt in range(3):
        before = tree_signature(root)
        try:
            with tarfile.open(destination, "w:gz", dereference=False) as archive:
                for path in entries(root):
                    archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
            if before == tree_signature(root):
                return None
            if live_log:
                return "Security logs changed during capture; this is a live copy"
        except (FileNotFoundError, OSError):
            if attempt == 2:
                raise BackupError("Source changed or could not be archived")
    raise BackupError("Media/audit source kept changing; retained incomplete staging")


def remote_verify(cfg, archive, remote):
    verification = archive.parent / "download-verification.age"
    run(["rclone", "--config", cfg["rclone_config"], "copyto", remote,
         str(verification), "--retries", "3", "--low-level-retries", "3",
         "--contimeout", "20s", "--timeout", "5m"])
    if sha256(archive) != sha256(verification):
        raise BackupError("Downloaded object checksum mismatch")
    verification.unlink()


def publish(cfg, archive, remote):
    run(["rclone", "--config", cfg["rclone_config"], "copyto", str(archive),
         remote, "--immutable", "--retries", "3", "--low-level-retries", "3",
         "--contimeout", "20s", "--timeout", "5m", "--s3-no-check-bucket"])
    remote_verify(cfg, archive, remote)


def heartbeat(cfg, suffix=""):
    path = cfg.get("heartbeat_file", "")
    if not path:
        raise BackupError("External monitoring heartbeat is not configured")
    url = Path(path).read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"https://hc-ping\.com/[a-fA-F0-9-]{36}", url):
        raise BackupError("Expected an HTTPS Healthchecks ping URL")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url + suffix, data=b"", method="POST")
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        if attempt < 2:
            time.sleep(2)
    raise BackupError("External heartbeat failed")


def cleanup(stage, now=None):
    """Delete only our completed, hash-verified run directories, never failed runs."""
    now = now or time.time()
    for directory in stage.iterdir():
        if not re.fullmatch(r"vsh-\d{8}T\d{6}Z-[0-9a-f]{12}", directory.name):
            continue
        if directory.is_symlink() or not directory.is_dir():
            continue
        if directory.resolve().parent != stage.resolve():
            continue
        receipt_path = directory / "verified.json"
        if not receipt_path.is_file() or receipt_path.is_symlink():
            continue
        try:
            receipt = json.loads(receipt_path.read_text())
            archive = directory / "backup.tar.gz.age"
            if now - receipt["verified_at"] < 3 * 86400:
                continue
            if archive.is_symlink() or sha256(archive) != receipt["sha256"]:
                continue
            # Refuse recursive removal if anything has become a symlink/special file.
            list(entries(directory))
        except (ValueError, KeyError, TypeError, OSError, BackupError):
            continue
        shutil.rmtree(directory)


def db_command(cfg, command):
    return ["docker", "exec", cfg["db_container"], "sh", "-c", command]


def check_source_mounts(cfg):
    mounts = json.loads(run(["docker", "inspect", "--format", "{{json .Mounts}}", cfg["app_container"]]))
    actual = {item["Destination"]: item["Source"] for item in mounts}
    for key, target in (("media", "/vol/web/media"), ("audit_archives", "/vol/audit-archives")):
        if actual.get(target) != cfg[key]:
            raise BackupError("Backup source does not match the application's Docker mount")


def create_backup(cfg, stage):
    check_source_mounts(cfg)
    now = datetime.now(timezone.utc)
    run_id = "vsh-" + now.strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    directory = stage / run_id
    directory.mkdir(mode=0o700)
    payload = directory / "payload"
    payload.mkdir(mode=0o700)
    warnings = ["Live backup: DB, globals and media are not a single atomic snapshot"]
    sources = {name: Path(cfg[name]) for name in ("media", "security_logs", "audit_archives")}
    source_size = sum(p.stat().st_size for root in sources.values() for p in entries(root) if p.is_file())
    run(db_command(cfg, 'exec pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'))
    db_size = int(run(db_command(cfg, 'exec psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pg_database_size(current_database())"')))
    reserve = int(cfg.get("min_free_gib", "5")) * 1024 ** 3
    require_space(stage, reserve + 4 * (source_size + db_size))
    print(f"{run_id}: database and globals", flush=True)
    database = payload / "database.dump"
    with database.open("wb") as output:
        run(db_command(cfg, 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'), output=output)
    with (payload / "globals.sql").open("wb") as output:
        run(db_command(cfg, 'exec pg_dumpall -U "$POSTGRES_USER" --globals-only'), output=output)
    with database.open("rb") as source:
        run(["docker", "exec", "-i", cfg["db_container"], "pg_restore", "--list"], input_file=source)
    if any(p.stat().st_size == 0 for p in (database, payload / "globals.sql")):
        raise BackupError("Empty database/globals backup")
    inventory = run(db_command(cfg, 'exec psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT datname FROM pg_database WHERE NOT datistemplate"'))
    database_name = run(db_command(cfg, 'exec psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database()"'))
    if set(inventory.splitlines()) - {database_name, "postgres"}:
        raise BackupError("Additional databases found; extend backup scope first")
    metadata = {
        "run_id": run_id, "created_utc": now.isoformat(),
        "created_vietnam": now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
        "database": database_name, "database_inventory": inventory.splitlines(),
        "postgres_version": run(db_command(cfg, "postgres --version")),
        "git_commit": run(["git", "-c", "safe.directory=" + cfg["repo"], "-C", cfg["repo"], "rev-parse", "HEAD"]),
        "db_image": run(["docker", "inspect", "--format", "{{.Image}}", cfg["db_container"]]),
        "sources": {k: str(v) for k, v in sources.items()}, "warnings": warnings,
        "excluded": ["Django .env", "Google JSON credentials", "Docker/containerd data roots", "postgres maintenance database contents", "custom PostgreSQL server configuration"],
    }
    print(f"{run_id}: media, logs, audit archives and selected configuration", flush=True)
    for name, source in sources.items():
        warning = archive_tree(source, payload / (name + ".tar.gz"), live_log=name == "security_logs")
        if warning:
            warnings.append(warning)
    config_dir = payload / "config"
    config_dir.mkdir()
    metadata["config_paths"] = {}
    for number, raw in enumerate(cfg["config_files"].splitlines()):
        if not raw.strip():
            continue
        source = Path(raw.strip())
        if source.is_symlink() or not source.is_file():
            raise BackupError("Required configuration file missing or symlink")
        target = config_dir / f"{number:02d}-{source.name}"
        shutil.copyfile(source, target)
        metadata["config_paths"][target.relative_to(payload).as_posix()] = str(source)
    files = {p.relative_to(payload).as_posix(): sha256(p) for p in payload.rglob("*") if p.is_file()}
    write_json(payload / "manifest.json", {**metadata, "sha256": files})
    plain = directory / "backup.tar.gz"
    archive_tree(payload, plain)
    archive = directory / "backup.tar.gz.age"
    print(f"{run_id}: encrypt, upload and download verification", flush=True)
    run(["age", "-R", cfg["recipient_file"], "-o", str(archive), str(plain)])
    require_space(stage, reserve + archive.stat().st_size)
    remote = cfg["remote"].rstrip("/") + "/" + now.strftime("%Y/%m/%d/") + run_id + ".tar.gz.age"
    publish(cfg, archive, remote)
    receipt = {"run_id": run_id, "verified_at": time.time(), "remote": remote,
               "sha256": sha256(archive), "bytes": archive.stat().st_size, "warnings": warnings}
    write_json(directory / "verified.json", receipt)
    write_json(stage / "last-success.json", receipt)
    # Exact freshly created paths; retain encrypted copy, remove plaintext after verification.
    plain.unlink()
    shutil.rmtree(payload)
    for warning in warnings:
        print(f"WARNING: {warning}", flush=True)
    print(f"{run_id}: VERIFIED {receipt['sha256']}", flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/vsh-backup/backup.ini"))
    parser.add_argument("--check", action="store_true", help="Check prerequisites without uploading")
    args = parser.parse_args()
    os.umask(0o077)
    cfg = None
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise BackupError("Run on the Linux host as root")
        private_file(args.config)
        cfg = read_config(args.config)
        for key in ("rclone_config", "recipient_file", "heartbeat_file"):
            private_file(Path(cfg[key]))
        if not re.fullmatch(r"[A-Za-z0-9_-]+:[a-z0-9.-]+/daily/orangepi/?", cfg["remote"]):
            raise BackupError("Remote must be remote:bucket/daily/orangepi")
        stage = check_mount(cfg)
        stage.mkdir(mode=0o700, exist_ok=True)
        if stage.stat().st_uid != 0 or stage.stat().st_mode & 0o077:
            raise BackupError("Staging must be root-owned mode 700")
        for executable in ("docker", "age", "rclone", "git"):
            if not shutil.which(executable):
                raise BackupError("Missing dependency: " + executable)
        with exclusive_lock(stage / ".lock"):
            if args.check:
                check_source_mounts(cfg)
                for key in ("media", "security_logs", "audit_archives"):
                    list(entries(Path(cfg[key])))
                run(db_command(cfg, 'exec pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'))
                print("Local prerequisites OK; R2, encryption/restore and monitoring still need acceptance tests")
                return 0
            create_backup(cfg, stage)
            heartbeat(cfg)
            cleanup(stage)
        return 0
    except Exception as exc:
        # Unexpected exception strings can include filenames/SQL/credentials.
        print("BACKUP FAILED: " + (str(exc) if isinstance(exc, BackupError) else type(exc).__name__), file=sys.stderr)
        if cfg and not args.check:
            try:
                heartbeat(cfg, "/fail")
            except Exception:
                print("Failure notification unavailable; external overdue monitor must alert", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
