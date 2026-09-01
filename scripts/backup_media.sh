#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${1:-$repo_root/vol/web/media}"
backup_dir="${2:-$repo_root/backups/media}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$backup_dir/vsh-media-$timestamp.tar.gz"

if [[ ! -d "$source_dir" ]]; then
  echo "Media directory does not exist: $source_dir" >&2
  exit 1
fi

mkdir -p "$backup_dir"
tar --create --gzip --file "$archive" --directory "$source_dir" .
sha256sum "$archive" > "$archive.sha256"

echo "Media backup created: $archive"
echo "Checksum created: $archive.sha256"
echo "Files archived: $(find "$source_dir" -type f | wc -l)"
