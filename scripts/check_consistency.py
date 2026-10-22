"""Check documented Python interfaces, file metadata, and frozen evidence hashes.

File: scripts/check_consistency.py
Maintainer: sunshine-engineer
Modified: 2026-10-23

Run python -m scripts.check_consistency from a Git checkout. This complements
Ruff: documentation presence does not establish that its descriptions are correct.
"""

import ast
import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_files():
    """List tracked and nonignored new project files without reading ignored secrets.

    Returns:
        list[Path]: Unique checkout paths relative to the repository root.

    Raises:
        subprocess.CalledProcessError: If this directory is not a usable Git checkout.
    """
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    return sorted({Path(name) for name in output.decode().split("\0") if name})


def python_errors(path):
    """Check module metadata and every declared class or callable, including nested helpers.

    Args:
        path: Repository-relative Python file path.

    Returns:
        list[str]: Documentation or metadata violations with file and line references.

    Raises:
        SyntaxError: If the file cannot be parsed as Python.
    """
    tree = ast.parse((ROOT / path).read_text(), filename=str(path))
    errors = []
    module_doc = ast.get_docstring(tree) or ""
    if (
        f"File: {path.as_posix()}" not in module_doc
        or "Maintainer: sunshine-engineer" not in module_doc
    ):
        errors.append(f"{path}: missing module file/maintainer metadata")
    modified = re.search(r"^Modified: (\d{4}-\d{2}-\d{2})$", module_doc, re.M)
    if not modified:
        errors.append(f"{path}: missing ISO modified date")
    else:
        date.fromisoformat(modified[1])
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            errors.append(f"{path}:{node.lineno}: {node.name} missing docstring")
            continue
        if isinstance(node, ast.ClassDef):
            continue
        parameters = [
            arg.arg
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            if arg.arg not in {"self", "cls"}
        ]
        if node.args.vararg:
            parameters.append("*" + node.args.vararg.arg)
        if node.args.kwarg:
            parameters.append("**" + node.args.kwarg.arg)
        for parameter in parameters:
            if not re.search(r"^\s+" + re.escape(parameter) + r":", doc, re.M):
                errors.append(f"{path}:{node.lineno}: {node.name} undocumented {parameter}")
    return errors


def evidence_errors():
    """Validate existing artifact checksums without rewriting frozen JSON records.

    Returns:
        tuple[list[str], int]: Hash violations and number of verified manifest entries.

    Raises:
        OSError: If an expected manifest or artifact is unavailable.
        json.JSONDecodeError: If a manifest cannot be decoded.
    """
    errors, checked = [], 0
    for name in (
        "report-manifest.json",
        "triage-manifest.json",
        "prospective-v1-results-manifest.json",
    ):
        manifest = json.loads((ROOT / "evaluation" / name).read_text())
        entries = manifest.get("files", {})
        entries = {**entries, **{row["path"]: row["sha256"] for row in manifest.get("runs", [])}}
        for relative, expected in entries.items():
            if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
                errors.append(f"{relative}: frozen artifact checksum mismatch")
            checked += 1
    freeze = json.loads((ROOT / "evaluation/prospective-v1-freeze.json").read_text())
    if (
        hashlib.sha256((ROOT / freeze["suite_file"]).read_bytes()).hexdigest()
        != freeze["suite_sha256"]
    ):
        errors.append("prospective suite differs from its pre-run freeze")
    return errors, checked


def main():
    """Run consistency and evidence-preservation checks without network or credentials.

    Returns:
        int: Zero if all files satisfy the checks; one if any violation is reported.
    """
    files = project_files()
    errors = []
    python_files = [path for path in files if path.suffix == ".py"]
    for path in python_files:
        errors.extend(python_errors(path))
    for path in files:
        if path.suffix == ".json":
            json.loads((ROOT / path).read_text())
    evidence, checked = evidence_errors()
    errors.extend(evidence)
    for error in errors:
        print(error)
    print(
        f"Checked {len(files)} project files, {len(python_files)} Python documentation contracts, "
        f"{checked} artifact hashes, and the prospective suite freeze; {len(errors)} errors."
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
