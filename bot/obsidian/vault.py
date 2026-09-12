"""Thin filesystem wrapper for reading/writing note files under the vault
root. All paths passed in are relative to the vault root; this is the only
module that touches the filesystem directly.
"""

from pathlib import Path


class VaultWriter:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def write_note(self, relative_path: str, content: str) -> Path:
        full_path = self._root / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return full_path

    def read_note(self, relative_path: str) -> str | None:
        full_path = self._root / relative_path
        if not full_path.exists():
            return None
        return full_path.read_text(encoding="utf-8")
