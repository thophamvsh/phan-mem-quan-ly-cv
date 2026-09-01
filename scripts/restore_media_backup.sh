#!/usr/bin/env bash
set -euo pipefail

archive="${1:?Usage: restore_media_backup.sh ARCHIVE EMPTY_TARGET_DIRECTORY}"
target="${2:?Usage: restore_media_backup.sh ARCHIVE EMPTY_TARGET_DIRECTORY}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/verify_media_backup.sh" "$archive"

if [[ -e "$target" ]] && [[ -n "$(find "$target" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Restore target must be empty to prevent overwriting media: $target" >&2
  exit 1
fi

mkdir -p "$target"
tar --extract --gzip --file "$archive" --directory "$target"

echo "Media restored into: $target"
echo "Review the restored files before changing the production media mount."
