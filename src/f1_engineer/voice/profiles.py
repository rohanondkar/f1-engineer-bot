from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from f1_engineer.config import VOICES_DIR, Gender, Region

# edge-tts locale voices as emergency fallback (man/woman-ish)
EDGE_VOICES: dict[tuple[str, str], str] = {
    ("us", "woman"): "en-US-AvaNeural",
    ("us", "man"): "en-US-AndrewNeural",
    ("uk", "woman"): "en-GB-SoniaNeural",
    ("uk", "man"): "en-GB-RyanNeural",
    ("spain", "woman"): "en-US-AvaMultilingualNeural",
    ("spain", "man"): "en-US-AndrewMultilingualNeural",
    ("italy", "woman"): "en-US-AvaMultilingualNeural",
    ("italy", "man"): "en-US-AndrewMultilingualNeural",
    ("brazil", "woman"): "en-US-AvaMultilingualNeural",
    ("brazil", "man"): "en-US-AndrewMultilingualNeural",
    ("germany", "woman"): "en-US-AvaMultilingualNeural",
    ("germany", "man"): "en-US-AndrewMultilingualNeural",
    ("japan", "woman"): "en-US-AvaMultilingualNeural",
    ("japan", "man"): "en-US-AndrewMultilingualNeural",
}


@dataclass
class VoiceProfile:
    id: str
    display_name: str
    gender: str
    region: str
    reference_wav: str = ""
    elevenlabs_voice_id: str = ""
    edge_voice: str = ""
    custom: bool = False
    notes: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def dir(self) -> Path:
        base = VOICES_DIR / ("custom" if self.custom else "")
        if self.custom:
            return VOICES_DIR / "custom" / self.id
        return VOICES_DIR / self.id

    def meta_path(self) -> Path:
        return self.dir / "profile.json"

    def reference_path(self) -> Path | None:
        if self.reference_wav:
            p = Path(self.reference_wav)
            if not p.is_absolute():
                p = self.dir / p
            return p if p.exists() else None
        cand = self.dir / "reference.wav"
        return cand if cand.exists() else None

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path().write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def _profile_from_dir(d: Path, custom: bool = False) -> VoiceProfile | None:
    meta = d / "profile.json"
    if meta.exists():
        data = json.loads(meta.read_text(encoding="utf-8"))
        return VoiceProfile(**{k: v for k, v in data.items() if k in VoiceProfile.__dataclass_fields__})
    # synthesize from folder name region_gender
    parts = d.name.split("_")
    if len(parts) >= 2:
        region, gender = parts[0], parts[1]
        return VoiceProfile(
            id=d.name,
            display_name=f"{region.upper()} {gender}",
            gender=gender,
            region=region,
            edge_voice=EDGE_VOICES.get((region, gender), "en-US-AvaNeural"),
            custom=custom,
        )
    return None


def list_profiles() -> list[VoiceProfile]:
    ensure_default_profiles()
    out: list[VoiceProfile] = []
    for d in sorted(VOICES_DIR.iterdir()):
        if d.is_dir() and d.name != "custom":
            p = _profile_from_dir(d, custom=False)
            if p:
                out.append(p)
    custom_root = VOICES_DIR / "custom"
    if custom_root.exists():
        for d in sorted(custom_root.iterdir()):
            if d.is_dir():
                p = _profile_from_dir(d, custom=True)
                if p:
                    out.append(p)
    return out


def get_profile(profile_id: str) -> VoiceProfile | None:
    for p in list_profiles():
        if p.id == profile_id:
            return p
    return None


def profile_for(region: Region, gender: Gender) -> VoiceProfile:
    ensure_default_profiles()
    pid = f"{region.value}_{gender.value}"
    p = get_profile(pid)
    if p:
        return p
    # fallback create
    return VoiceProfile(
        id=pid,
        display_name=f"{region.value.upper()} {gender.value}",
        gender=gender.value,
        region=region.value,
        edge_voice=EDGE_VOICES.get((region.value, gender.value), "en-US-AvaNeural"),
    )


def import_voice(
    wav_path: Path,
    display_name: str,
    gender: Gender,
    region: Region,
    profile_id: str | None = None,
) -> VoiceProfile:
    pid = profile_id or f"custom_{gender.value}_{region.value}_{display_name.lower().replace(' ', '_')}"
    dest = VOICES_DIR / "custom" / pid
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "reference.wav"
    shutil.copy2(wav_path, target)
    profile = VoiceProfile(
        id=pid,
        display_name=display_name,
        gender=gender.value,
        region=region.value,
        reference_wav="reference.wav",
        edge_voice=EDGE_VOICES.get((region.value, gender.value), "en-US-AvaNeural"),
        custom=True,
        notes="User-imported clone reference",
    )
    profile.save()
    return profile


def ensure_default_profiles() -> None:
    """Create metadata for region×gender packs. Reference WAVs optional until generated."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    (VOICES_DIR / "custom").mkdir(parents=True, exist_ok=True)
    for region in Region:
        for gender in Gender:
            pid = f"{region.value}_{gender.value}"
            d = VOICES_DIR / pid
            d.mkdir(parents=True, exist_ok=True)
            meta = d / "profile.json"
            if not meta.exists():
                VoiceProfile(
                    id=pid,
                    display_name=f"{region.name.title()} {gender.value.title()}",
                    gender=gender.value,
                    region=region.value,
                    edge_voice=EDGE_VOICES.get((region.value, gender.value), "en-US-AvaNeural"),
                    notes="Shipped pack — add reference.wav for local/ElevenLabs cloning",
                ).save()
            # placeholder note if no reference
            readme = d / "README.txt"
            if not readme.exists():
                readme.write_text(
                    "Place a 10–30s clean reference.wav here for zero-shot / Instant Voice Clone.\n"
                    "Until then, edge-tts or a global clone backend is used.\n",
                    encoding="utf-8",
                )
