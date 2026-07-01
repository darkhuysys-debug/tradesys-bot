#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
VER=${1:-$(cat VERSION)}
TARBALL="/tmp/TradeSys_update_${VER}.tar.gz"

python3 -c "
import json, subprocess, os
os.chdir(os.path.dirname(os.path.abspath('$0')))
out = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)
excludes = {'.gitignore', 'backups', '__pycache__', '.pyc', 'build_release.sh', '.git', 'version.json'}
files = []
for line in out.stdout.strip().split('\n'):
    p = line.strip()
    if p and not any(x in p for x in excludes):
        files.append({'path': p, 'type': 'stable', 'note': ''})
with open('version.json', 'w') as f:
    json.dump({'version': '$VER', 'files': files}, f, indent=2)
print(f'version.json with {len(files)} files')
"

tar czf "$TARBALL" \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='build_release.sh' \
  $(git ls-files) version.json

echo "Release tarball: $TARBALL ($(tar tzf "$TARBALL" | wc -l) files)"
