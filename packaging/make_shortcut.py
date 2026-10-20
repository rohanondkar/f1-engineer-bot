"""Create a Desktop shortcut to dist/F1EngineerBot/F1EngineerBot.exe."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    exe = root / "dist" / "F1EngineerBot" / "F1EngineerBot.exe"
    if not exe.exists():
        print(f"EXE not found: {exe}", file=sys.stderr)
        return 1

    desktop = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
    shortcut = desktop / "F1 Engineer Bot.lnk"

    # Prefer PowerShell COM (no pywin32 required on Windows)
    ps = f"""
$W = New-Object -ComObject WScript.Shell
$S = $W.CreateShortcut('{shortcut.as_posix()}')
$S.TargetPath = '{exe.as_posix()}'
$S.WorkingDirectory = '{exe.parent.as_posix()}'
$S.Description = 'AI F1 Race Engineer'
$S.Save()
Write-Output 'Desktop shortcut: {shortcut.as_posix()}'
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(result.stdout.strip() or f"Desktop shortcut: {shortcut}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
