"""Run plain .sql migration files through Alembic (asyncpg executes one statement per call)."""


def _strip_comment(line: str) -> str:
    """Remove a trailing `-- comment`, ignoring `--` inside single-quoted strings."""
    in_string = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'":
            in_string = not in_string
        elif not in_string and line.startswith("--", i):
            return line[:i]
        i += 1
    return line


def statements(sql: str) -> list[str]:
    """Split a SQL script into statements. Comments are dropped first, so a semicolon inside a
    comment can't break a statement; semicolons inside string literals are not supported."""
    cleaned = "\n".join(_strip_comment(line) for line in sql.splitlines())
    return [part.strip() for part in cleaned.split(";") if part.strip()]
