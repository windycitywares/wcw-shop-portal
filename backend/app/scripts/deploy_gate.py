"""Asked by deploy/auto-deploy.sh on every cron run: should the server look for updates now?

    python -m app.scripts.deploy_gate begin            # prints "go <reason>" or "skip <reason>"
    python -m app.scripts.deploy_gate end ok|failed SUMMARY

`begin` always exits 0 (the script reads the first word); if it prints nothing usable, the script looks for updates
anyway, so a broken gate never stops deploys.
"""

from __future__ import annotations

import asyncio
import sys


async def _main(argv: list[str]) -> str:
    from app.core.database import engine
    from app.services.deploy import DeployService

    try:
        service = DeployService(engine)
        if argv[:1] == ["begin"]:
            d = await service.gate_begin()
            return f"{'go' if d.go else 'skip'} {d.reason}"
        if argv[:1] == ["end"] and len(argv) >= 2:
            await service.gate_end(argv[1] == "ok", " ".join(argv[2:]))
            return "recorded"
        return "usage: deploy_gate begin | end ok|failed SUMMARY"
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print(asyncio.run(_main(sys.argv[1:])))
