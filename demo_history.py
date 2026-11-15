"""Deterministic FICTIONAL measurement history for the demo astronauts.

ALL DATA HERE ARE FICTIONAL and describe no real person. Running
`python demo_history.py [--db PATH]` replaces the history of the demo astronauts with
about five years of readings, so every dashboard range (1D ... 5Y, All) has data.
Fixed seeds and a fixed END make the output identical on every run.
"""

import argparse
import math
import random
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType

from Caracteristici import (
    CHARACTERISTIC_DEFINITIONS,
    DB_PATH,
    Characteristic,
    column_name,
    create_table,
)

END = datetime(2026, 11, 14, 18, 0)
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
SEED_BASE = 20261114
MISSION_DAYS = 180
MISSION_START = END - timedelta(days=MISSION_DAYS)
HISTORY_DAYS = 5 * 365 + 14

RECENT_HOURS = 48
RECENT_STEP_HOURS = 3
DAILY_FIRST_DAY = 2
DAILY_LAST_DAY = 120
WEEKLY_STEP_DAYS = 7
DAILY_TIME = time(9, 0)
MINUTES_PER_ASTRONAUT_STEP = 15
SETTLE_DAYS = 21  # noise fades out over the last weeks so the final reading is exact
MIN_ANOMALY_AGE_DAYS = 30
ANOMALY_COUNT_RANGE = (2, 4)
CIRCADIAN_HR_AMPLITUDE = 4.0  # bpm, peak about 6 h before the last reading
HEIGHT_GAIN_CM = 1.5  # in-flight spinal elongation: height before the mission is lower
WEIGHT_LOSS_KG = 0.5  # weight before the mission was slightly higher
RADIATION_RATE_MSV_PER_DAY = 0.3
RADIATION_PRE_MISSION_RANGE = (0.1, 2.0)
SYSTOLIC_MIN_GAP = 20
MUSCLE_PLUS_FAT_MAX = 90.0

_C = Characteristic
INTEGER_CHARACTERISTICS = frozenset({_C.AGE, _C.AVERAGE_HEART_RATE, _C.SYSTOLIC_BLOOD_PRESSURE, _C.DIASTOLIC_BLOOD_PRESSURE, _C.BLOOD_GLUCOSE})
LIMITS = MappingProxyType(
    {d.characteristic: (d.minimum, d.maximum) for d in CHARACTERISTIC_DEFINITIONS}
)

# Change over the five years before the mission (value at mission start minus value 5 years ago).
PRE_MISSION_CHANGE: Mapping[Characteristic, float] = MappingProxyType(
    {
        Characteristic.AVERAGE_HEART_RATE: 1.0,
        Characteristic.SYSTOLIC_BLOOD_PRESSURE: 3.0,
        Characteristic.DIASTOLIC_BLOOD_PRESSURE: 2.0,
        Characteristic.MUSCLE_MASS_PERCENTAGE: -1.0,
        Characteristic.BODY_FAT_PERCENTAGE: 1.0,
        Characteristic.STRESS_LEVEL: 0.0,
        Characteristic.BLOOD_GLUCOSE: 2.0,
        Characteristic.SLEEP_HOURS: 0.0,
        Characteristic.BONE_DENSITY_CALCIUM: -0.03,
    }
)
DAY_NOISE_SD: Mapping[Characteristic, float] = MappingProxyType(
    {
        Characteristic.AVERAGE_HEART_RATE: 2.5,
        Characteristic.SYSTOLIC_BLOOD_PRESSURE: 3.0,
        Characteristic.DIASTOLIC_BLOOD_PRESSURE: 2.0,
        Characteristic.MUSCLE_MASS_PERCENTAGE: 0.3,
        Characteristic.BODY_FAT_PERCENTAGE: 0.4,
        Characteristic.STRESS_LEVEL: 0.5,
        Characteristic.BLOOD_GLUCOSE: 4.0,
        Characteristic.SLEEP_HOURS: 0.35,
        Characteristic.BONE_DENSITY_CALCIUM: 0.008,
        Characteristic.BODY_WEIGHT: 0.3,
        Characteristic.HEIGHT: 0.15,
    }
)


@dataclass(frozen=True)
class DemoProfile:
    first_name: str
    last_name: str
    age: int  # latest age (stored on the astronaut row)
    height: float  # latest height, cm
    weight: float  # latest weight, kg
    seed_index: int
    # Characteristic -> (value at MISSION_START, value at the end).
    mission: Mapping[Characteristic, tuple[float, float]]


@dataclass(frozen=True)
class Spike:
    """An isolated one-reading anomaly: add `add`, or replace the value with `set_to`."""

    characteristic: Characteristic
    add: float = 0.0
    set_to: float | None = None


@dataclass(frozen=True)
class Timeline:
    history_start: datetime
    mission_start: datetime
    anchor: datetime  # last reading of this astronaut (END minus the minute offset)


SPIKES: tuple[Spike, ...] = (
    Spike(Characteristic.AVERAGE_HEART_RATE, add=25),
    Spike(Characteristic.BLOOD_GLUCOSE, add=90),
    Spike(Characteristic.SLEEP_HOURS, set_to=4.5),
    Spike(Characteristic.STRESS_LEVEL, add=4),
)


def _mission(
    heart_rate: tuple[float, float],
    systolic: tuple[float, float],
    diastolic: tuple[float, float],
    muscle: tuple[float, float],
    fat: tuple[float, float],
    stress: tuple[float, float],
    glucose: tuple[float, float],
    sleep: tuple[float, float],
    bone: tuple[float, float],
) -> Mapping[Characteristic, tuple[float, float]]:
    return MappingProxyType(
        {
            Characteristic.AVERAGE_HEART_RATE: heart_rate,
            Characteristic.SYSTOLIC_BLOOD_PRESSURE: systolic,
            Characteristic.DIASTOLIC_BLOOD_PRESSURE: diastolic,
            Characteristic.MUSCLE_MASS_PERCENTAGE: muscle,
            Characteristic.BODY_FAT_PERCENTAGE: fat,
            Characteristic.STRESS_LEVEL: stress,
            Characteristic.BLOOD_GLUCOSE: glucose,
            Characteristic.SLEEP_HOURS: sleep,
            Characteristic.BONE_DENSITY_CALCIUM: bone,
        }
    )


DEMO_PROFILES: tuple[DemoProfile, ...] = (
    DemoProfile(
        "Vega", "Lyra", 42, 180, 78, 0,
        _mission(
            heart_rate=(64, 65), systolic=(117, 118), diastolic=(75, 76),
            muscle=(42.5, 42.0), fat=(17.5, 18.0), stress=(2.3, 2.0),
            glucose=(90, 88), sleep=(7.9, 7.8), bone=(1.19, 1.14),
        ),
    ),
    DemoProfile(
        "Kai", "Orion", 36, 175, 72, 1,
        _mission(
            heart_rate=(68, 69), systolic=(128, 132), diastolic=(80, 82),
            muscle=(41.0, 40.0), fat=(20.0, 21.0), stress=(6.2, 6.9),
            glucose=(92, 95), sleep=(6.5, 6.0), bone=(1.15, 1.12),
        ),
    ),
    DemoProfile(
        "Nova", "Sirius", 45, 168, 67, 2,
        _mission(
            heart_rate=(100, 106), systolic=(92, 86), diastolic=(60, 56),
            muscle=(38.5, 37.0), fat=(16.0, 17.0), stress=(3.0, 3.0),
            glucose=(98, 105), sleep=(7.4, 7.2), bone=(1.18, 1.02),
        ),
    ),
    DemoProfile(
        "Lynx", "Ara", 39, 172, 70, 3,
        _mission(
            heart_rate=(70, 72), systolic=(130, 186), diastolic=(84, 112),
            muscle=(40.0, 39.0), fat=(19.0, 20.0), stress=(4.0, 4.0),
            glucose=(88, 50), sleep=(7.2, 7.0), bone=(1.20, 1.17),
        ),
    ),
)


# --- Schedule ----------------------------------------------------------------------------
def _reading_times(end: datetime, offset: timedelta) -> tuple[datetime, ...]:
    """Every 3 h for 48 h, one 09:00 reading per day for days 2..120, then weekly."""
    anchor = end - offset
    recent = [anchor - timedelta(hours=RECENT_STEP_HOURS * k) for k in range(RECENT_HOURS // RECENT_STEP_HOURS + 1)]
    daily_base = datetime.combine(end.date(), DAILY_TIME) + offset
    daily = [daily_base - timedelta(days=d) for d in range(DAILY_LAST_DAY, DAILY_FIRST_DAY - 1, -1)]
    weekly = [daily_base - timedelta(days=d) for d in range(HISTORY_DAYS, DAILY_LAST_DAY, -WEEKLY_STEP_DAYS)]
    return tuple(sorted([*recent, *daily, *weekly]))


def _choose_spikes(
    rng: random.Random, times: Sequence[datetime], anchor: datetime
) -> dict[int, Spike]:
    """Pick 2-4 isolated past readings (older than MIN_ANOMALY_AGE_DAYS) and one effect each."""
    candidates = [i for i, when in enumerate(times) if (anchor - when).days >= MIN_ANOMALY_AGE_DAYS]
    count = rng.randint(*ANOMALY_COUNT_RANGE)
    indexes = rng.sample(candidates, count)
    effects = rng.sample(SPIKES, count)
    return dict(zip(indexes, effects))


# --- Values ------------------------------------------------------------------------------
def _fraction(when: datetime, start: datetime, stop: datetime) -> float:
    span = (stop - start).total_seconds()
    return min(1.0, max(0.0, (when - start).total_seconds() / span))


def _trend(pre: float, final: float, change: float, when: datetime, timeline: Timeline) -> float:
    """Piecewise-linear trend: slow drift before the mission, then drift toward the final value."""
    if when < timeline.mission_start:
        fraction = _fraction(when, timeline.history_start, timeline.mission_start)
        return pre - change * (1 - fraction)
    return pre + (final - pre) * _fraction(when, timeline.mission_start, timeline.anchor)


def _circadian(when: datetime, anchor: datetime) -> float:
    """Heart-rate day cycle that is exactly zero at the last reading."""
    hour_of_day = when.hour + when.minute / 60
    reference = anchor.hour + anchor.minute / 60
    return CIRCADIAN_HR_AMPLITUDE * math.sin(2 * math.pi * (hour_of_day - reference) / 24)


def _settle(when: datetime, anchor: datetime) -> float:
    """1 far in the past, 0 at the last reading: noise fades in the final weeks."""
    days_to_anchor = (anchor - when).total_seconds() / 86400
    return min(1.0, days_to_anchor / SETTLE_DAYS)


def _raw_values(
    profile: DemoProfile,
    timeline: Timeline,
    when: datetime,
    rng: random.Random,
    pre_dose: float,
) -> dict[Characteristic, float]:
    settle = _settle(when, timeline.anchor)
    values: dict[Characteristic, float] = {}
    for characteristic, change in PRE_MISSION_CHANGE.items():
        pre, final = profile.mission[characteristic]
        level = _trend(pre, final, change, when, timeline)
        values[characteristic] = level + rng.gauss(0.0, DAY_NOISE_SD[characteristic]) * settle
    values[Characteristic.AVERAGE_HEART_RATE] += _circadian(when, timeline.anchor)
    demographics = (
        (Characteristic.BODY_WEIGHT, profile.weight + WEIGHT_LOSS_KG, profile.weight),
        (Characteristic.HEIGHT, profile.height - HEIGHT_GAIN_CM, profile.height),
    )
    for characteristic, pre, final in demographics:
        level = _trend(pre, final, 0.0, when, timeline)
        values[characteristic] = level + rng.gauss(0.0, DAY_NOISE_SD[characteristic]) * settle
    days_in_mission = max(0.0, (when - timeline.mission_start).total_seconds() / 86400)
    values[Characteristic.MISSION_RADIATION_LEVEL] = pre_dose + RADIATION_RATE_MSV_PER_DAY * days_in_mission
    values[Characteristic.AGE] = float(profile.age - (timeline.anchor - when).days // 365)
    return values


def _apply_spike(values: Mapping[Characteristic, float], spike: Spike) -> dict[Characteristic, float]:
    current = values[spike.characteristic]
    new_value = spike.set_to if spike.set_to is not None else current + spike.add
    return {**values, spike.characteristic: new_value}


def _round_and_clamp(characteristic: Characteristic, value: float) -> float:
    if characteristic in INTEGER_CHARACTERISTICS:
        rounded = float(round(value))
    elif characteristic is Characteristic.BONE_DENSITY_CALCIUM:
        rounded = round(value, 3)
    else:
        rounded = round(value, 1)
    low, high = LIMITS[characteristic]
    return min(high, max(low, rounded))


def _finalise(values: Mapping[Characteristic, float]) -> dict[Characteristic, float]:
    """Round, clamp and enforce the cross-field rules (BMI from weight/height, BP gap, fat sum)."""
    rounded = {c: _round_and_clamp(c, v) for c, v in values.items()}
    rounded[Characteristic.SYSTOLIC_BLOOD_PRESSURE] = _round_and_clamp(
        Characteristic.SYSTOLIC_BLOOD_PRESSURE,
        max(
            rounded[Characteristic.SYSTOLIC_BLOOD_PRESSURE],
            rounded[Characteristic.DIASTOLIC_BLOOD_PRESSURE] + SYSTOLIC_MIN_GAP,
        ),
    )
    weight = rounded[Characteristic.BODY_WEIGHT]
    height = rounded[Characteristic.HEIGHT]
    rounded[Characteristic.BODY_MASS_INDEX] = _round_and_clamp(
        Characteristic.BODY_MASS_INDEX, round(weight / (height / 100) ** 2, 1)
    )
    muscle = rounded[Characteristic.MUSCLE_MASS_PERCENTAGE]
    if muscle + rounded[Characteristic.BODY_FAT_PERCENTAGE] > MUSCLE_PLUS_FAT_MAX:
        rounded[Characteristic.BODY_FAT_PERCENTAGE] = MUSCLE_PLUS_FAT_MAX - muscle
    return {c: rounded[c] for c in (d.characteristic for d in CHARACTERISTIC_DEFINITIONS)}


def generate_history(
    profile: DemoProfile, end: datetime = END
) -> tuple[tuple[str, Mapping[Characteristic, float]], ...]:
    """Oldest-first (recorded_at, values) rows for one astronaut; deterministic for a profile."""
    offset = timedelta(minutes=profile.seed_index * MINUTES_PER_ASTRONAUT_STEP)
    times = _reading_times(end, offset)
    timeline = Timeline(
        history_start=end - timedelta(days=HISTORY_DAYS),
        mission_start=end - timedelta(days=MISSION_DAYS),
        anchor=end - offset,
    )
    rng = random.Random(SEED_BASE + profile.seed_index)
    pre_dose = rng.uniform(*RADIATION_PRE_MISSION_RANGE)
    spikes = _choose_spikes(rng, times, timeline.anchor)
    rows = []
    for index, when in enumerate(times):
        values = _raw_values(profile, timeline, when, rng, pre_dose)
        if index in spikes:
            values = _apply_spike(values, spikes[index])
        rows.append((when.strftime(TIMESTAMP_FORMAT), MappingProxyType(_finalise(values))))
    return tuple(rows)


# --- Database ----------------------------------------------------------------------------
MEASUREMENT_COLUMNS: tuple[str, ...] = tuple(
    column_name(d.characteristic) for d in CHARACTERISTIC_DEFINITIONS
)
INSERT_SQL = (
    "INSERT INTO measurement_history (astronaut_id, recorded_at, "
    + ", ".join(MEASUREMENT_COLUMNS)
    + ") VALUES ("
    + ", ".join("?" for _ in range(len(MEASUREMENT_COLUMNS) + 2))
    + ")"
)


def _upsert_astronaut(conn: sqlite3.Connection, profile: DemoProfile) -> int:
    row = conn.execute(
        "SELECT id FROM astronauts WHERE first_name = ? AND last_name = ?",
        (profile.first_name, profile.last_name),
    ).fetchone()
    if row is None:
        cursor = conn.execute(
            "INSERT INTO astronauts (first_name, last_name, age, height, weight) VALUES (?, ?, ?, ?, ?)",
            (profile.first_name, profile.last_name, profile.age, profile.height, profile.weight),
        )
        return int(cursor.lastrowid or 0)
    conn.execute(
        "UPDATE astronauts SET age = ?, height = ?, weight = ? WHERE id = ?",
        (profile.age, profile.height, profile.weight, row[0]),
    )
    return int(row[0])


def _insert_rows(
    conn: sqlite3.Connection, astronaut_id: int, history: Sequence[tuple[str, Mapping[Characteristic, float]]]
) -> None:
    conn.execute("DELETE FROM measurement_history WHERE astronaut_id = ?", (astronaut_id,))
    conn.executemany(
        INSERT_SQL,
        [
            (astronaut_id, recorded_at, *(values[d.characteristic] for d in CHARACTERISTIC_DEFINITIONS))
            for recorded_at, values in history
        ],
    )


def seed_database(
    conn: sqlite3.Connection,
    profiles: Sequence[DemoProfile] = DEMO_PROFILES,
    end: datetime = END,
) -> dict[str, int]:
    """Replace the history of the given profiles in one transaction; returns rows per "Last First"."""
    create_table(conn)
    # Covers the latest-row lookup (id last keeps ORDER BY sorted) and the Avg HR AVG() per astronaut.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_measurement_history_astronaut_time "
        "ON measurement_history (astronaut_id, recorded_at, id, average_pulse)"
    )
    counts: dict[str, int] = {}
    with conn:
        for profile in profiles:
            history = generate_history(profile, end)
            astronaut_id = _upsert_astronaut(conn, profile)
            _insert_rows(conn, astronaut_id, history)
            counts[f"{profile.last_name} {profile.first_name}"] = len(history)
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill the demo astronauts with fictional history.")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="database file to write")
    args = parser.parse_args(argv)
    with closing(sqlite3.connect(args.db)) as conn:
        counts = seed_database(conn)
    for name, count in counts.items():
        print(f"{name}: {count} rows written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
