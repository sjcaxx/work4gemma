"""Build the existing agent config as a ZIP and an importable Kaggle notebook."""
import base64
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notes/official_kit/submission"
OUT = ROOT / "dist"


def main():
    OUT.mkdir(exist_ok=True)
    archive = OUT / "submission.zip"
    files = sorted(p for p in SOURCE.rglob("*") if p.is_file())
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, path.relative_to(SOURCE).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert "agent.yaml" in z.namelist()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT / "submission.zip.sha256").write_text(digest + "  submission.zip\n")
    metadata = {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "submission_sha256": digest,
        "submission_files": len(files),
        "official_inference_run": False,
        "kaggle_submission_id": None,
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    payload = base64.b64encode(archive.read_bytes()).decode()
    code = f'''from pathlib import Path
import base64, hashlib, zipfile
out = Path("/kaggle/working/submission.zip")
out.write_bytes(base64.b64decode({payload!r}))
assert hashlib.sha256(out.read_bytes()).hexdigest() == {digest!r}
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert "agent.yaml" in z.namelist()
print("Built:", out, "SHA-256:", hashlib.sha256(out.read_bytes()).hexdigest())
print("This notebook packages the agent. Only the competition evaluator provides a score.")
'''
    notebook = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python", "version": "3.12"}},
        "cells": [
            {"id": "instructions", "cell_type": "markdown", "metadata": {}, "source": [
                "# CodeArch submission builder\n",
                "Import into a private notebook attached to the main Gemma 4 Developer Agent competition.\n",
                "Run the cell, save a version, then select submission.zip in the competition submission dialog.\n",
                "This builds the existing multi-agent configuration; it does not measure repair accuracy.\n",
                "No GPU, Internet access, or external credentials are required to build the ZIP.\n"]},
            {"id": "package", "cell_type": "code", "metadata": {}, "execution_count": None,
             "outputs": [], "source": code.splitlines(keepends=True)},
        ],
    }
    (OUT / "CodeArch_Kaggle.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    print(archive)


if __name__ == "__main__":
    main()
