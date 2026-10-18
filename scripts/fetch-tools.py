#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
sources = json.loads((root / 'sources.json').read_text())
for name in ('mysticgsi', 'treble_app'):
    source = sources[name]
    dest = root / 'toolchains' / name
    dest.mkdir(parents=True, exist_ok=False)
    for args in (
        ['git', 'init', '-q', str(dest)],
        ['git', '-C', str(dest), 'remote', 'add', 'origin', source['url']],
        ['git', '-C', str(dest), 'fetch', '--depth=1', 'origin', source['commit']],
        ['git', '-C', str(dest), 'checkout', '--detach', 'FETCH_HEAD'],
    ):
        subprocess.run(args, check=True)
    actual = subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == source['commit'], (name, actual)
subprocess.run(['python3', '-m', 'pip', 'install', '-r', str(root / 'toolchains/mysticgsi/requirements.txt')], check=True)
(root / 'artifacts').mkdir(exist_ok=True)
with (root / 'artifacts/python-packages.txt').open('w') as stream:
    subprocess.run(['python3', '-m', 'pip', 'freeze'], stdout=stream, check=True)
