# AI F1 Race Engineer (F1 26)

Voice + text race engineer companion for **F1 26** on Steam. Listens to live UDP telemetry, speaks proactive team-radio calls, answers push-to-talk / typed questions, and supports multiple engineer personas (man/woman) with regional English accents and clonable voices.

## Features

- Live F1 26 UDP telemetry ingest
- Proactive radio (gaps, tires, fuel, SC, damage, pace)
- CommsGate: priority, cooldowns, brake-aware mute, talkativeness
- Personas: strategist, aggressive, data geek, veteran — each with man/woman presentation
- Regions: US, UK, Spain, Italy, Brazil, Germany, Japan
- Text transcript + type-to-engineer chat
- Voice: ElevenLabs clone → local XTTS/F5 clone → edge-tts fallback
- Optional team-radio FX
- Always-on-top overlay + system tray

## Steam / F1 26 telemetry setup

1. Launch **F1 26** (Steam).
2. **Settings → Telemetry**
3. Set:
   - **UDP Telemetry:** On
   - **UDP IP Address:** `127.0.0.1`
   - **UDP Port:** `20777`
   - **UDP Send Rate:** 60 Hz
   - **UDP Format:** `2026` (Season Pack) or `2025`
4. Start a session, then run this app.

## Install

```powershell
cd "G:\F1 Engineer Bot"
python -m venv .venv
# If Activate.ps1 is blocked by execution policy, skip activation and use the full path below
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
# Edit .env — at least OPENAI_API_KEY for LLM replies
```

Optional local clone TTS (GPU recommended):

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[xtts]"
```

## Run without a terminal (EXE)

Build once (several minutes; large because of PySide6 + Whisper deps):

```bat
build_exe.bat
```

Then double-click:

- `dist\F1EngineerBot\F1EngineerBot.exe`, or
- the **F1 Engineer Bot** shortcut on your Desktop

No PowerShell window opens. Edit API keys in `dist\F1EngineerBot\.env` (next to the exe). `voices\` and `data\` live there too.

## Run from project (dev)

```bat
run.bat
run.bat --mock
```

Or without activating the venv:

```powershell
cd "G:\F1 Engineer Bot"
.\.venv\Scripts\python.exe -m f1_engineer
.\.venv\Scripts\python.exe -m f1_engineer --mock
```

If you want `Activate.ps1` for this session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
f1-engineer
```

## Overlay controls

- **PTT** — hold configured hotkey (default `` ` `` / grave) to talk
- **Text box** — type questions without PTT
- **Persona / Gender / Region / Voice** — pick your engineer
- **Talkativeness** — Quiet / Normal / Chatty
- **Mute** — silence TTS, keep transcript
- **Import voice** — drop a WAV to create a custom clone profile

## Voice cloning

- Shipped packs live under `voices/` (region × gender).
- Custom imports go to `voices/custom/` (gitignored).
- With `ELEVENLABS_API_KEY`, Instant Voice Clone is preferred.
- Without it, local zero-shot clone runs if `[xtts]` extras are installed; otherwise edge-tts is used with a quality warning.

Importing samples of real people is your responsibility — only use audio you have rights to.

## Config

See [`.env.example`](.env.example). Rapport scores are stored in `data/rapport.json`.
