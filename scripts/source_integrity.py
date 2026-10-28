#!/usr/bin/env python3
"""Read-only encoding check and SHA-256 inventory of Git-tracked repository files.

Web pages and diagrams are UTF-8, not ASCII-only. Credentials are separate.
The report contains file paths and hashes, not private untracked source content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

TEXT_SUFFIXES = frozenset({
    '.css', '.csv', '.drawio', '.dot', '.graphql', '.htm', '.html', '.ini',
    '.ipynb', '.js', '.json', '.jsonl', '.jsx', '.md', '.mdx', '.mermaid',
    '.mjs', '.mmd', '.puml', '.py', '.sh', '.sql', '.svg', '.toml',
    '.ts', '.tsx', '.txt', '.xml', '.yaml', '.yml',
})
TEXT_FILENAMES = frozenset({
    '.editorconfig', '.gitattributes', '.gitignore', '.python-version',
    'Dockerfile', 'Makefile', 'Procfile', 'requirements.txt',
})


def is_text_path(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def inspect_file(path: Path, content: bytes) -> dict:
    result = {
        'path': path.as_posix(),
        'bytes': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
        'kind': 'text' if is_text_path(path) else 'binary-or-other',
    }
    if result['kind'] != 'text':
        result.update(encoding='not-applicable', status='NOT_TEXT_CHECKED')
        return result
    try:
        content.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        result.update(encoding='invalid', status='INVALID_UTF8', error_byte=exc.start)
        return result
    if b'\x00' in content:
        result.update(encoding='invalid', status='NUL_IN_TEXT')
        return result
    if content.startswith(b'\xef\xbb\xbf'):
        if path.suffix.lower() != '.csv':
            result.update(encoding='utf-8-bom', status='BOM_IN_SOURCE')
            return result
        result.update(encoding='utf-8-bom', status='VALID_UTF8')
        return result
    result.update(encoding='utf-8', status='VALID_UTF8')
    return result


def tracked_paths() -> list[Path]:
    data = subprocess.run(['git', 'ls-files', '-z'], check=True, stdout=subprocess.PIPE).stdout
    return [Path(item.decode('utf-8', errors='surrogateescape'))
            for item in data.split(b'\x00') if item]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('source-integrity-manifest.json'))
    args = parser.parse_args()
    entries = [inspect_file(path, path.read_bytes()) for path in sorted(tracked_paths())]
    failures = [x for x in entries if x['status'] not in {'VALID_UTF8', 'NOT_TEXT_CHECKED'}]
    report = {
        'schema': 'GENESIS-SOURCE-INTEGRITY-R0.1',
        'source': 'git-ls-files',
        'scope': 'tracked-repository-files-only',
        'tracked_files': len(entries),
        'validated_text_files': sum(x['status'] == 'VALID_UTF8' for x in entries),
        'binary_or_other_files': sum(x['status'] == 'NOT_TEXT_CHECKED' for x in entries),
        'failures': len(failures),
        'entries': entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print('Source integrity: {tracked_files} tracked, {validated_text_files} UTF-8 text, '
          '{binary_or_other_files} other, {failures} failures'.format(**report))
    for result in failures:
        print('{path}: {status} {error_byte}'.format(
            path=result['path'], status=result['status'],
            error_byte=result.get('error_byte', '')))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
