"""
Traceability test — AC-5.

Every significant module (except __init__.py, conftest.py) must carry a rule
reference comment '# R{n}' or '# R{n}.' in its module-level docstring or
first 20 lines, pointing to rulebook v1 rule it implements.
"""
import ast
import os
import re
import pytest


# Modules exempt from traceability requirement
EXEMPT = {"__init__.py", "conftest.py", "setup.py", "benchmark.py"}

# Rule-ref pattern: matches '# R1', '# R2', ..., '# R8', '# R3.1' etc.
RULE_REF_RE = re.compile(r"#\s*R[1-8](?:\.\d+)?")

PACKAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "cubrim_proto")


def get_package_modules() -> list[str]:
    """Return list of .py files in cubrim_proto/ that are not exempt."""
    modules = []
    for fname in sorted(os.listdir(PACKAGE_DIR)):
        if fname.endswith(".py") and fname not in EXEMPT:
            modules.append(os.path.join(PACKAGE_DIR, fname))
    return modules


def has_rule_ref(filepath: str) -> bool:
    """Return True if the file contains a rule reference in its first 30 lines."""
    with open(filepath, encoding="utf-8") as f:
        lines = [f.readline() for _ in range(30)]
    content = "".join(lines)
    return bool(RULE_REF_RE.search(content))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_all_modules_have_rule_reference():
    """
    AC-5: every cubrim_proto/*.py (except exempt list) must have a # R{n} rule
    reference in its first 30 lines (module docstring or header comment).
    """
    missing = []
    modules = get_package_modules()
    assert modules, "No modules found in cubrim_proto/ — package not built yet?"
    for path in modules:
        if not has_rule_ref(path):
            missing.append(os.path.basename(path))

    assert not missing, (
        f"The following modules lack a rulebook rule reference (# R<n>):\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def test_expected_modules_exist():
    """All plan-specified modules must exist in cubrim_proto/."""
    expected = [
        "phi.py", "cube.py", "distance_map.py", "rle.py",
        "bitpack.py", "header.py", "codec.py", "domainize.py",
    ]
    for name in expected:
        path = os.path.join(PACKAGE_DIR, name)
        assert os.path.exists(path), f"Expected module {name} not found in cubrim_proto/"
