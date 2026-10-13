#!/usr/bin/env python3
"""Offline verification on a clean machine; never executes SQL or restored files."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

from backup_daily import BackupError, run, sha256


def unpack(archive, destination, limit=20 * 1024 ** 3):
    if destination.exists():
        raise BackupError("Extraction destination must not already exist")
    destination.mkdir(mode=0o700, parents=True)
    total = 0
    seen = set()
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts
                    or "\\" in member.name or ":" in member.name
                    or not (member.isfile() or member.isdir()) or member.name in seen):
                raise BackupError("Unsafe or duplicate archive entry")
            seen.add(member.name)
            total += member.size
            if total > limit or len(seen) > 1000000:
                raise BackupError("Archive exceeds extraction limits")
            target = destination.joinpath(*path.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise BackupError("Archive entry escapes destination")
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open("xb") as output:
                    shutil.copyfileobj(incoming, output)


def verify_payload(payload):
    manifest = json.loads((payload / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest["sha256"]
    actual = {p.relative_to(payload).as_posix(): p for p in payload.rglob("*") if p.is_file()}
    actual.pop("manifest.json", None)
    if set(actual) != set(expected):
        raise BackupError("Manifest file list mismatch")
    for name, path in actual.items():
        if sha256(path) != expected[name]:
            raise BackupError("Payload checksum mismatch")
    required = {"database.dump", "globals.sql", "media.tar.gz", "security_logs.tar.gz", "audit_archives.tar.gz"}
    if not required.issubset(actual):
        raise BackupError("Required backup component missing")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="Recorded independently at backup time")
    parser.add_argument("--output", type=Path, required=True, help="New directory on clean machine")
    args = parser.parse_args()
    os.umask(0o077)
    if sha256(args.archive) != args.sha256.lower():
        raise BackupError("Encrypted archive checksum mismatch")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    plain = args.output / "decrypted.tar.gz"
    run(["age", "-d", "-i", str(args.identity), "-o", str(plain), str(args.archive)])
    payload = args.output / "payload"
    unpack(plain, payload)
    manifest = verify_payload(payload)
    unpack(payload / "media.tar.gz", args.output / "media")
    print("Decryption and manifest verified:", manifest["run_id"])
    print("Database restore, role/permission review and media-reference checks are still required.")


if __name__ == "__main__":
    main()
