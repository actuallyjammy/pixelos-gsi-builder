#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
donor = json.loads((root / 'sources.json').read_text())['donor']
dest = root / 'downloads'
dest.mkdir(exist_ok=True)
path = dest / donor['filename']
for url in [donor['url'], *donor.get('mirrors', [])]:
    print(f'Trying donor source: {url}', flush=True)
    result = subprocess.run([
        'curl', '--fail', '--location', '--retry', '2', '--connect-timeout', '30',
        '--max-time', '1200', '--speed-limit', '1024', '--speed-time', '60',
        '--output', str(path), url,
    ])
    if result.returncode or path.stat().st_size != donor['size']:
        print('Download failed or unexpected size; trying the next official mirror.', flush=True)
        path.unlink(missing_ok=True)
        continue
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != donor['sha256']:
        path.unlink()
        raise SystemExit(f'Donor SHA256 mismatch: {digest}')
    (root / 'artifacts').mkdir(exist_ok=True)
    (root / 'artifacts/donor-source.json').write_text(json.dumps({'url': url, 'sha256': digest}, indent=2) + '\n')
    print(f'Verified donor SHA256: {digest}', flush=True)
    break
else:
    raise SystemExit('All official donor download sources failed.')
