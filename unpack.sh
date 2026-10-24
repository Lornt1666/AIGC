#!/usr/bin/env bash
set -euo pipefail
OUTPUT_FILE="${1:-response.md}"
[ -f "$OUTPUT_FILE" ] || { printf '[-] Error: target file %s not found\nUsage: ./unpack.sh <saved_response.md>\n' "$OUTPUT_FILE" >&2; exit 1; }
python3 - "$OUTPUT_FILE" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()
i = 0
created = []
while i < len(source):
    line = source[i]
    if not line.startswith('### FILE: `') or not line.endswith('`'):
        i += 1
        continue
    name = line[len('### FILE: `'):-1]
    target = Path(name)
    if target.is_absolute() or '..' in target.parts:
        raise SystemExit(f'Refusing unsafe output path: {name}')
    i += 1
    while i < len(source) and not source[i].startswith('```'):
        i += 1
    if i >= len(source):
        raise SystemExit(f'Missing opening code fence for {name}')
    i += 1
    content = []
    while i < len(source) and not source[i].startswith('```'):
        content.append(source[i])
        i += 1
    if i >= len(source):
        raise SystemExit(f'Missing closing code fence for {name}')
    i += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(content) + '\n', encoding='utf-8')
    created.append(name)
for name in created:
    print('[+] Created: ' + name)
if not created:
    raise SystemExit('No FILE blocks found.')
print(f'[+] Extracted {len(created)} files.')
PY
printf '[+] To initialize: chmod +x bootstrap.sh && ./bootstrap.sh\n'
