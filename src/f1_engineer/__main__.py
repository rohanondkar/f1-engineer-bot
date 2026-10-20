from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AI F1 Race Engineer for F1 26")
    parser.add_argument("--mock", action="store_true", help="Use mock telemetry")
    parser.add_argument("--headless", action="store_true", help="No overlay (console radio log)")
    parser.add_argument("--text", type=str, default="", help="Send one text question then exit (headless)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from f1_engineer.app import EngineerApp
    from f1_engineer.config import get_settings

    settings = get_settings()
    if args.mock:
        settings.mock_telemetry = True

    app = EngineerApp(settings=settings)

    if args.headless or args.text:
        asyncio.run(_headless(app, args.text))
        return

    from f1_engineer.ui.overlay import run_overlay

    sys.exit(run_overlay(app))


async def _headless(app: EngineerApp, one_shot: str) -> None:
    def on_msg(m) -> None:
        print(f"[{m.kind}] {m.speaker}: {m.text}")

    app.radio_log.subscribe(on_msg)
    await app.start()
    if one_shot:
        await asyncio.sleep(1.5)
        await app.handle_driver_text(one_shot)
        await asyncio.sleep(1.0)
        await app.stop()
        return

    print("Headless engineer running. Ctrl+C to stop. Type messages and press Enter.")
    try:
        while True:
            try:
                line = await asyncio.to_thread(input, "> ")
            except EOFError:
                break
            if line.strip().lower() in {"quit", "exit"}:
                break
            if line.strip():
                await app.handle_driver_text(line.strip())
    except KeyboardInterrupt:
        pass
    finally:
        await app.stop()


if __name__ == "__main__":
    main()
