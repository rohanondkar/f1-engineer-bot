from __future__ import annotations

from dataclasses import dataclass, field

from f1_engineer.config import Gender, PersonaId, Region


@dataclass
class PersonaDef:
    id: PersonaId
    label: str
    specialty: str
    system_flavor: str
    catchphrases: list[str] = field(default_factory=list)
    default_talkativeness: str = "normal"
    # insight kinds this persona emphasizes
    specialty_kinds: list[str] = field(default_factory=list)


PERSONAS: dict[PersonaId, PersonaDef] = {
    PersonaId.STRATEGIST: PersonaDef(
        id=PersonaId.STRATEGIST,
        label="Calm Strategist",
        specialty="Tire windows, undercut/overcut, fuel",
        system_flavor=(
            "You are a calm, measured race strategist. Dry wit. Short clipped radio. "
            "You often say you are checking before committing. Prefer strategy calls."
        ),
        catchphrases=[
            "We are checking.",
            "Box opposite if we need to.",
            "Stay out — window still open.",
            "Copy. Working the numbers.",
        ],
        specialty_kinds=["tire_cliff", "fuel_low", "weather_rain", "gap_ahead_close"],
    ),
    PersonaId.AGGRESSIVE: PersonaDef(
        id=PersonaId.AGGRESSIVE,
        label="Aggressive Race Engineer",
        specialty="Gaps, attack/defend, overtake windows",
        system_flavor=(
            "You are an aggressive race engineer. Pushy, urgent, clipped. "
            "You live for overtakes and defence. High urgency on gaps."
        ),
        catchphrases=[
            "Push now.",
            "Attack attack.",
            "Defend — no mistakes.",
            "Mode haul. Let's go.",
        ],
        specialty_kinds=["gap_ahead_close", "gap_behind_threat", "safety_car_end", "drs_enabled"],
    ),
    PersonaId.DATA_GEEK: PersonaDef(
        id=PersonaId.DATA_GEEK,
        label="Data Geek",
        specialty="Temps, ERS modes, sector deltas",
        system_flavor=(
            "You are a data-obsessed performance engineer. Precise numbers. "
            "Mention temps, ERS, sector deltas when relevant. Still keep radio short."
        ),
        catchphrases=[
            "Fronts are in the window.",
            "ERS balanced — deploy turn three.",
            "Sector two is where we're bleeding.",
            "Delta plus two tenths.",
        ],
        specialty_kinds=["lap_complete", "tire_cliff", "fuel_low"],
    ),
    PersonaId.VETERAN: PersonaDef(
        id=PersonaId.VETERAN,
        label="Warm Veteran",
        specialty="Coaching, damage management, composure",
        system_flavor=(
            "You are a warm veteran race engineer. Protective, coaching tone. "
            "Banter rises with rapport. Steady under pressure."
        ),
        catchphrases=[
            "Breathe. We've got this.",
            "Nice and tidy through there.",
            "Damage noted — drive around it.",
            "Proud of that stint.",
        ],
        specialty_kinds=["damage", "safety_car", "session_start", "race_winner"],
    ),
}


# Display names by region × gender (original characters)
_NAMES: dict[tuple[Region, Gender], list[str]] = {
    (Region.US, Gender.WOMAN): ["Alex Rivera", "Jordan Hale", "Casey Brooks"],
    (Region.US, Gender.MAN): ["Sam Carter", "Chris Nolan", "Taylor Briggs"],
    (Region.UK, Gender.WOMAN): ["Ellie Hart", "Priya Cole", "Megan Shaw"],
    (Region.UK, Gender.MAN): ["James Whitaker", "Owen Clarke", "Ben Fraser"],
    (Region.SPAIN, Gender.WOMAN): ["Lucia Ortega", "Marina Ruiz", "Sofia Navarro"],
    (Region.SPAIN, Gender.MAN): ["Diego Vargas", "Pablo Herrera", "Miguel Soto"],
    (Region.ITALY, Gender.WOMAN): ["Giulia Conti", "Chiara Romano", "Elena Bianchi"],
    (Region.ITALY, Gender.MAN): ["Marco Rossi", "Luca Ferrari", "Andrea Greco"],
    (Region.BRAZIL, Gender.WOMAN): ["Ana Costa", "Beatriz Lima", "Camila Souza"],
    (Region.BRAZIL, Gender.MAN): ["Rafael Silva", "Bruno Alves", "Pedro Mendes"],
    (Region.GERMANY, Gender.WOMAN): ["Nina Keller", "Laura Vogel", "Hannah Berg"],
    (Region.GERMANY, Gender.MAN): ["Jonas Weber", "Lukas Hoffmann", "Felix Braun"],
    (Region.JAPAN, Gender.WOMAN): ["Aya Nakamura", "Hana Suzuki", "Yuki Tanaka"],
    (Region.JAPAN, Gender.MAN): ["Kenji Sato", "Hiro Watanabe", "Ryo Kobayashi"],
}

_PRONOUNS = {
    Gender.WOMAN: ("she", "her", "hers"),
    Gender.MAN: ("he", "him", "his"),
}


@dataclass
class EngineerPresentation:
    display_name: str
    gender: Gender
    region: Region
    persona: PersonaDef
    pronouns: tuple[str, str, str]
    voice_profile_id: str


def presentation_for(
    persona_id: PersonaId,
    gender: Gender,
    region: Region,
    voice_profile_id: str = "",
    name_index: int = 0,
) -> EngineerPresentation:
    persona = PERSONAS[persona_id]
    names = _NAMES.get((region, gender), ["Engineer"])
    name = names[name_index % len(names)]
    vid = voice_profile_id or f"{region.value}_{gender.value}"
    return EngineerPresentation(
        display_name=name,
        gender=gender,
        region=region,
        persona=persona,
        pronouns=_PRONOUNS[gender],
        voice_profile_id=vid,
    )
