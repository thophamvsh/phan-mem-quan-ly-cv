#!/usr/bin/env bash
set -euo pipefail

archive="${1:?Usage: verify_media_backup.sh /path/to/vsh-media-*.tar.gz}"
checksum="$archive.sha256"

if [[ ! -f "$archive" || ! -f "$checksum" ]]; then
  echo "Archive or checksum file is missing." >&2
  exit 1
fi

(cd "$(dirname "$archive")" && sha256sum --check "$(basename "$checksum")")
tar --list --gzip --file "$archive" >/dev/null

echo "Media backup is readable and checksum is valid: $archive"
