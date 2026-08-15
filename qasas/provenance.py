from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import platform
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_SCOPE = (
    "qasas/**/*.py",
    "qasas_cli.py",
    "QASAS_app.pyw",
    "requirements.txt",
)


@dataclass(frozen=True, slots=True)
class FileProvenance:
    path: Path
    sha256: str
    size_bytes: int
    modified_at: str


def file_sha256(path: str | Path) -> str:
    source = Path(path)
    digest = sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_provenance(path: str | Path) -> FileProvenance:
    """Hash one input file and reject a file that changes during hashing."""

    source = Path(path).resolve()
    before = source.stat()
    digest = file_sha256(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"Input file changed while calculating SHA-256: {source}")
    return FileProvenance(
        path=source,
        sha256=digest,
        size_bytes=after.st_size,
        modified_at=datetime.fromtimestamp(after.st_mtime).astimezone().isoformat(
            timespec="seconds"
        ),
    )


def file_provenance_rows(prefix: str, item: FileProvenance) -> tuple[tuple[str, object], ...]:
    return (
        (f"{prefix} file", str(item.path)),
        (f"{prefix} SHA-256", item.sha256),
        (f"{prefix} size (bytes)", item.size_bytes),
        (f"{prefix} modified time", item.modified_at),
    )


def application_source_sha256(root: str | Path = REPOSITORY_ROOT) -> str:
    """Hash the runtime Python source and dependency declaration deterministically."""

    repository = Path(root).resolve()
    paths: set[Path] = set()
    for pattern in _SOURCE_SCOPE:
        paths.update(path for path in repository.glob(pattern) if path.is_file())
    digest = sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(repository).as_posix()):
        relative = path.relative_to(repository).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _git_output(*arguments: str) -> str | None:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
            env=environment,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unavailable"


def runtime_provenance_rows() -> tuple[tuple[str, object], ...]:
    commit = os.environ.get("QASAS_GIT_COMMIT") or _git_output("rev-parse", "HEAD")
    status = _git_output(
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        "qasas",
        "qasas_cli.py",
        "QASAS_app.pyw",
        "requirements.txt",
    )
    if status is None:
        worktree = "unavailable"
    else:
        worktree = "clean" if not status else "modified"
    return (
        ("Repository Git commit", commit or "unavailable"),
        ("Git working tree", worktree),
        ("Application source SHA-256", application_source_sha256()),
        ("Application source hash scope", "; ".join(_SOURCE_SCOPE)),
        ("Python version", platform.python_version()),
        ("openpyxl version", _package_version("openpyxl")),
        ("matplotlib version", _package_version("matplotlib")),
        ("Operating system", platform.platform()),
        ("Provenance timing", "Calculated automatically when this Excel file was exported"),
    )

