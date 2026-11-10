"""Every data file under ``daypart/`` ships in the wheel (HAC-38, CTO hand-back 3172f7da).

The hosted demo installs the engine as a wheel (``deploy/modal_demo.py``: ``uv pip install /app``),
so a data file that ``[tool.setuptools.package-data]`` does not list is missing there, while an
editable install (CI, local runs) still finds it on disk. That is how ``sources_v1.json`` went
missing and the hosted passport returned 500 from the P2 land until this fix.

This test applies setuptools' rule without building a wheel: a non-Python file is shipped only if
a glob listed for its nearest enclosing package matches its path relative to that package.
"""

from __future__ import annotations

import fnmatch
import tomllib
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[2]
PKG_ROOT = ENGINE / "daypart"


def _package_data() -> dict[str, list[str]]:
    cfg = tomllib.loads((ENGINE / "pyproject.toml").read_text("utf-8"))
    return cfg["tool"]["setuptools"]["package-data"]


def _data_files() -> list[Path]:
    return sorted(
        p
        for p in PKG_ROOT.rglob("*")
        if p.is_file() and p.suffix not in {".py", ".pyc"} and "__pycache__" not in p.parts
    )


def _nearest_package(path: Path) -> Path:
    d = path.parent
    while not (d / "__init__.py").exists():
        assert d != PKG_ROOT.parent, f"{path} is not inside a package"
        d = d.parent
    return d


def _shipped(path: Path, package_data: dict[str, list[str]]) -> bool:
    pkg = _nearest_package(path)
    name = ".".join(pkg.relative_to(ENGINE).parts)
    rel = path.relative_to(pkg).as_posix()
    # setuptools globs match per path segment: "*" does not cross "/".
    return any(
        rel.count("/") == g.count("/") and fnmatch.fnmatchcase(rel, g) for g in package_data.get(name, [])
    )


def test_data_files_exist():
    # Guard: an empty scan would make the next test pass vacuously.
    assert len(_data_files()) >= 10


@pytest.mark.parametrize("path", _data_files(), ids=lambda p: p.relative_to(ENGINE).as_posix())
def test_every_data_file_is_package_data(path: Path):
    assert _shipped(path, _package_data()), (
        f"{path.relative_to(ENGINE)} is not in [tool.setuptools.package-data], so the wheel the "
        "hosted demo installs will not contain it"
    )


def test_evidence_sources_listed():
    # The file whose absence broke the hosted passport (evidence/registry.py reads it).
    assert _shipped(PKG_ROOT / "evidence" / "sources_v1.json", _package_data())


def test_rule_rejects_unlisted_file():
    # The rule itself must be able to fail: an unlisted package or a non-matching glob is not shipped.
    assert not _shipped(PKG_ROOT / "evidence" / "sources_v1.json", {})
    assert not _shipped(PKG_ROOT / "membrane" / "rules" / "boundary-v1.yaml", {"daypart.membrane": ["*.yaml"]})
