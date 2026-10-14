import unittest
from pathlib import Path

from app.utils.sqlfile import statements

SQL_DIR = Path(__file__).resolve().parents[1] / "migrations" / "sql"


class SqlFileTests(unittest.TestCase):
    def test_splits_and_drops_comments(self):
        sql = "-- header; with semicolon\nCREATE TABLE a (x int); -- trailing; note\nINSERT INTO a VALUES ('--not a comment');\n"
        self.assertEqual(statements(sql), ["CREATE TABLE a (x int)", "INSERT INTO a VALUES ('--not a comment')"])

    def test_every_migration_file_splits_into_complete_statements(self):
        files = sorted(SQL_DIR.glob("*.sql"))
        self.assertTrue(files)
        for f in files:
            parts = statements(f.read_text(encoding="utf-8"))
            self.assertTrue(parts, f.name)
            for part in parts:
                first = part.split(None, 1)[0].upper()
                self.assertIn(first, {"CREATE", "ALTER", "UPDATE", "INSERT", "DROP", "COMMENT"}, f"{f.name}: {part[:60]}")
                self.assertEqual(part.count("("), part.count(")"), f"{f.name}: unbalanced parentheses in {part[:60]}")


if __name__ == "__main__":
    unittest.main()
