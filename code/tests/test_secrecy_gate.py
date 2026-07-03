"""
Secrecy gate test — AC-7 / V-AC-5.

Binds the secrecy gate to the pytest green-bar contract.

Rule (task-description § Секретность): public Diataxis surface
  documentation/{tutorials,how-to,reference,explanation}/ and README*
must contain zero mechanism-disclosure terms. The grep returns
exit code 1 (no matches) = gate passes; exit code 0 (matches found)
= gate fails (mechanism leaked).

ephemeral/ is intentionally excluded from this gate — research notes
live there and are not public.
"""
import re
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Secrecy gate
# ---------------------------------------------------------------------------

# Repo root is two levels above this file (code/tests/ -> code/ -> repo root)
_REPO_ROOT = Path(__file__).resolve().parents[2]

_PUBLIC_DIRS = [
    "documentation/tutorials",
    "documentation/how-to",
    "documentation/reference",
    "documentation/explanation",
]

_PATTERN = (
    r"distance-map|карт[аеуы] расстоян|bit-pack|gap-to-next"
    r"|N-мерн|n-dimensional cube|edge bound"
)


def test_secrecy_gate_public_docs_empty():
    """
    AC-7: public Diataxis surface must carry zero mechanism-disclosure terms.
    grep exit 0 (matches found) → FAIL; exit 1 (no matches) or exit 2
    (path absent — directories don't exist yet) → PASS (no mechanism present).
    """
    targets = [str(_REPO_ROOT / d) for d in _PUBLIC_DIRS]
    # Also probe README* at repo root
    readme_glob = list(_REPO_ROOT.glob("README*"))

    cmd = [
        "grep", "-rin", "-E", _PATTERN,
        *targets,
        *[str(p) for p in readme_glob],
    ]

    result = subprocess.run(cmd, capture_output=True)

    # exit 0 = matches found → leak → FAIL
    assert result.returncode != 0, (
        "Secrecy gate FAILED — mechanism terms found in public docs:\n"
        + result.stdout.decode(errors="replace")
    )
