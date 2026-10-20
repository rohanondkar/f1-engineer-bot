# Voice packs

Each folder is a voice profile: `{region}_{gender}` plus optional `custom/` imports.

## Layout

```
voices/
  us_woman/
    profile.json
    reference.wav   # optional 10–30s clean speech for cloning
  us_man/
  ...
  custom/
    your_clone/
      profile.json
      reference.wav
```

## Natural cloning

1. Drop a clear `reference.wav` into a pack (or use **Import WAV** in the overlay).
2. With `ELEVENLABS_API_KEY`, Instant Voice Clone is created automatically.
3. Or install local cloning: `pip install -e ".[xtts]"` (GPU recommended).
4. Without a reference, the app falls back to edge-tts (lower quality).

Only import samples you have rights to use.
