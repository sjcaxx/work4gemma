"""Verify the immutable archive and optionally extract it for CPU-only review."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(extract=False):
    provenance = json.loads((ROOT / 'provenance.json').read_text(encoding='utf-8'))
    archive = ROOT / 'raw-artifacts.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == provenance['raw_archive_sha256']
    output = (ROOT / 'runner/remote-v2').resolve()
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == provenance['raw_files_including_download_manifest']
        rows = json.loads(z.read('download-manifest.json'))
        for row in rows:
            content = z.read(row['file'])
            assert len(content) == row['bytes'], row['file']
            assert hashlib.sha256(content).hexdigest() == row['sha256'], row['file']
        if extract:
            for entry in z.infolist():
                target = (output / entry.filename).resolve()
                if not target.is_relative_to(output):
                    raise ValueError('Unsafe archive path')
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(entry))
    print(f'Verified {len(rows)} Kaggle artifacts; archive SHA-256 matches.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true')
    verify(parser.parse_args().extract)
