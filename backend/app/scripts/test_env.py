"""Test mode from the command line (used by deploy/update-api.sh after migrations).

    python -m app.scripts.test_env status
    python -m app.scripts.test_env sync-if-active   # after a migration: refresh the test copy so it has the new tables
    python -m app.scripts.test_env live             # emergency: switch the shop back to live data
"""

import asyncio
import json
import sys
from types import SimpleNamespace

from app.core.database import engine
from app.services.testenv import TestEnvironment

DEPLOY = SimpleNamespace(id=None, email="deploy@server")


async def main(command: str) -> int:
    env = TestEnvironment(engine)
    try:
        state = await env.status()
        if command == "status":
            print(json.dumps(state, default=str, indent=2))
        elif command == "sync-if-active":
            if state["mode"] == "test" and state["out_of_date"]:
                print("Test mode is on and the test data is out of date: copying the live data again")
                print(json.dumps(await env.sync(DEPLOY, switch_on=False)))  # type: ignore[arg-type]
            else:
                print("Nothing to do")
        elif command == "live":
            await env.switch("live", DEPLOY)  # type: ignore[arg-type]
            print("Switched to live data")
        else:
            print(__doc__)
            return 2
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
