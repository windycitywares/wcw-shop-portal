"""Database backups from the command line.

    python -m app.scripts.backup now                           # back up the live data now
    python -m app.scripts.backup list                          # the backups in the GitHub repository
    python -m app.scripts.backup decrypt FILE.dump.enc OUT.dump  # turn a downloaded backup back into a pg_dump file

`decrypt` reads BACKUP_PASSPHRASE from backend/.env (or asks for it). Then restore with pg_restore, see
docs/DEPLOYMENT.md → "Backups".
"""

import asyncio
import getpass
import json
import sys
from pathlib import Path


async def _now() -> int:
    from app.core.database import engine
    from app.services.backups import BackupService

    try:
        result = await BackupService(engine).run("manual", "command line")
    finally:
        await engine.dispose()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


async def _list() -> int:
    from app.core.database import engine
    from app.services.backups import BackupService

    try:
        for f in await BackupService(engine).remote_files():
            print(f"{f['name']}  {round((f['size'] or 0) / 1e6, 1)} MB")
    finally:
        await engine.dispose()
    return 0


def _decrypt(source: str, target: str) -> int:
    from app.core.config import get_settings
    from app.services.backups import BackupError, decrypt

    passphrase = get_settings().backup_passphrase or getpass.getpass("Backup passphrase: ")
    try:
        data = decrypt(Path(source).read_bytes(), passphrase)
    except BackupError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    out = Path(target)
    if out.exists():
        print(f"✗ {target} already exists", file=sys.stderr)
        return 1
    out.write_bytes(data)
    print(f"✓ {target} ({round(len(data) / 1e6, 1)} MB). Restore it with pg_restore (docs/DEPLOYMENT.md → Backups).")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["now"]:
        return asyncio.run(_now())
    if argv[:1] == ["list"]:
        return asyncio.run(_list())
    if argv[:1] == ["decrypt"] and len(argv) == 3:
        return _decrypt(argv[1], argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
