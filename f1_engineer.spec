# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: windowed onedir build for F1EngineerBot.exe"""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

block_cipher = None
ROOT = Path(SPECPATH)

datas: list = []
binaries: list = []
hiddenimports: list = [
    "f1_engineer",
    "f1_engineer.__main__",
    "f1_engineer.app",
    "f1_engineer.config",
    "f1_engineer.ui.overlay",
    "f1_engineer.voice.stt",
    "f1_engineer.voice.tts_backends",
    "f1_engineer.voice.manager",
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "av",
    "edge_tts",
    "miniaudio",
    "sounddevice",
    "soundfile",
    "keyboard",
    "openai",
    "httpx",
    "pydantic",
    "pydantic_settings",
    "dotenv",
]

# Heavy UI + audio stacks
for pkg in ("PySide6", "shiboken6", "faster_whisper", "ctranslate2", "onnxruntime"):
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

try:
    binaries += collect_dynamic_libs("sounddevice")
except Exception:
    pass

# Exclude optional local-clone stack (torch / Coqui) to keep size down
excludes = [
    "torch",
    "torchaudio",
    "torchvision",
    "TTS",
    "tensorflow",
    "jax",
    "matplotlib",
    "IPython",
    "notebook",
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="F1EngineerBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="F1EngineerBot",
)
