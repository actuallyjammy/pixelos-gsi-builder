#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
donor = json.loads((root / 'sources.json').read_text())['donor']
dest = root / 'downloads'
dest.mkdir(exist_ok=True)
subprocess.run(['aria2c', '--check-certificate=true', '-x8', '-s8', '--max-tries=4', '--retry-wait=10', '--dir', str(dest), '--out', donor['filename'], donor['url']], check=True)
path = dest / donor['filename']
assert path.stat().st_size == donor['size'], 'Donor size mismatch'
with path.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
assert digest == donor['sha256'], f'Donor SHA256 mismatch: {digest}'
print(f'Verified donor SHA256: {digest}', flush=True)
