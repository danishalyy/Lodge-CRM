"""Docker uses the lock file, so new direct dependencies must be locked too."""

from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]


def requirements(filename):
    return [
        Requirement(line.strip())
        for line in (ROOT / filename).read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_docker_lock_covers_every_direct_dependency():
    locked = {
        canonicalize_name(requirement.name): requirement
        for requirement in requirements("requirements.lock.txt")
    }
    for requirement in requirements("requirements.txt"):
        name = canonicalize_name(requirement.name)
        assert name in locked, f"{requirement.name} is missing from Docker's lock file"
        pins = list(locked[name].specifier)
        assert len(pins) == 1 and pins[0].operator == "==", name
        assert requirement.specifier.contains(pins[0].version), (
            f"{requirement} conflicts with Docker's {locked[name]}"
        )
