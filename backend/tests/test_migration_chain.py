"""The Alembic revisions form one unbroken chain, and every SQL file a migration runs exists.

Pure file parsing (no Alembic or database needed), so the server's pre-deploy unit tests catch a broken chain
before `alembic upgrade head` is attempted.
"""

import ast
import re
import unittest
from pathlib import Path

VERSIONS = Path(__file__).resolve().parent.parent / "migrations" / "versions"
SQL = VERSIONS.parent / "sql"


def _assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


class MigrationChainTests(unittest.TestCase):
    def setUp(self):
        self.files = sorted(p for p in VERSIONS.glob("*.py") if not p.name.startswith("__"))
        self.revs = {p.name: _assignments(p) for p in self.files}

    def test_single_linear_chain(self):
        ids = {v["revision"] for v in self.revs.values()}
        self.assertEqual(len(ids), len(self.files), "duplicate revision ids")
        parents = [v["down_revision"] for v in self.revs.values()]
        self.assertEqual(parents.count(None), 1, "exactly one base revision")
        for name, v in self.revs.items():
            if v["down_revision"] is not None:
                self.assertIn(v["down_revision"], ids, f"{name}: down_revision points at an unknown revision")
        self.assertEqual(len(set(p for p in parents if p)), len(parents) - 1, "a revision has two children (branch)")
        # Walk from the base: every revision is reached once.
        child = {v["down_revision"]: v["revision"] for v in self.revs.values()}
        seen, current = [], child.get(None)
        while current:
            seen.append(current)
            current = child.get(current)
        self.assertEqual(len(seen), len(self.files))

    def test_header_matches_code(self):
        for path in self.files:
            v = self.revs[path.name]
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
            self.assertIn(f"Revision ID: {v['revision']}", doc, path.name)
            if v["down_revision"]:
                self.assertIn(f"Revises: {v['down_revision']}", doc, path.name)

    def test_sql_files_exist(self):
        for path in self.files:
            for ref in re.findall(r'_run\("([^"]+)"\)', path.read_text(encoding="utf-8")):
                self.assertTrue((SQL / ref).exists(), f"{path.name} runs missing {ref}")


if __name__ == "__main__":
    unittest.main()
