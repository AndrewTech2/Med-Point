"""Tests for the terminal dashboard (dashboard_terminal.py) and demo data (dashboard_demo_data.py).

All data used here is fictional or created in pytest's tmp_path. The astronauti database
is never opened for writing and is never read by these tests.

DISCLAIMER: thresholds are informational; confirm them with the flight surgeon / medical team.
"""

import io
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from types import MappingProxyType

import pytest

import dashboard_terminal
from Caracteristici import (
    CHARACTERISTIC_DEFINITIONS,
    Characteristic as C,
    create_table,
    save_astronaut,
)
from dashboard_demo_data import DEMO_ASTRONAUTS, AstronautRecord
from dashboard_terminal import (
    ANSI_RESET,
    DISCLAIMER,
    colorize,
    load_db_astronauts,
    main,
    parse_args,
    render_astronaut,
    render_report,
    should_use_color,
)
from recommendation_types import MissionPhase, Status
from recommendations import assess

HEALTHY_CORE: dict[C, float] = {
    C.AGE: 42,
    C.BODY_WEIGHT: 78,
    C.HEIGHT: 180,
    C.BODY_MASS_INDEX: 24.1,
    C.AVERAGE_HEART_RATE: 65,
    C.SYSTOLIC_BLOOD_PRESSURE: 118,
    C.DIASTOLIC_BLOOD_PRESSURE: 76,
    C.MUSCLE_MASS_PERCENTAGE: 42,
    C.BODY_FAT_PERCENTAGE: 18,
    C.STRESS_LEVEL: 2,
    C.MISSION_RADIATION_LEVEL: 40,
    C.BONE_DENSITY_CALCIUM: 1.2,
    C.BLOOD_GLUCOSE: 88,
    C.SLEEP_HOURS: 7.8,
}

EXPECTED_OVERALL: dict[str, Status] = {
    "Vega Lyra": Status.OK,
    "Kai Orion": Status.WATCH,
    "Nova Sirius": Status.ACTION,
    "Draco Altair": Status.URGENT,
    "Pavo Rigel": Status.UNKNOWN,
}


def _name(record: AstronautRecord) -> str:
    return f"{record.last_name} {record.first_name}"


def _record_by_name(name: str) -> AstronautRecord:
    return next(r for r in DEMO_ASTRONAUTS if _name(r) == name)


def _demo_assessment(record: AstronautRecord):
    return assess(record.values, record.phase or MissionPhase.UNKNOWN)


def _make_db(directory: Path) -> Path:
    """Create a real astronauti table with one valid astronaut inside tmp_path."""
    path = directory / "astronauti.db"
    with closing(sqlite3.connect(path)) as conn:
        create_table(conn)
        save_astronaut(conn, "Test", "Ana", dict(HEALTHY_CORE))
    return path


def _make_old_style_db(directory: Path) -> Path:
    """A database created before the characteristic columns existed."""
    path = directory / "old.db"
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute(
                "CREATE TABLE astronauti (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "nume TEXT NOT NULL, prenume TEXT NOT NULL)"
            )
            conn.execute("INSERT INTO astronauti (nume, prenume) VALUES ('Old', 'Row')")
    return path


class FakeTTY:
    """Stream stub whose isatty() reports a terminal."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def no_no_color_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("NO_COLOR", raising=False)
    yield


# --- Rendering without colour -------------------------------------------------------------


class TestRenderWithoutColor:
    def test_report_contains_no_ansi_escape_codes(self) -> None:
        # Arrange
        records = DEMO_ASTRONAUTS

        # Act
        output = render_report(records, None, use_color=False)

        # Assert
        assert "\x1b[" not in output

    def test_report_starts_with_disclaimer(self) -> None:
        # Arrange / Act
        output = render_report(DEMO_ASTRONAUTS, None, use_color=False)

        # Assert
        assert DISCLAIMER in output
        assert output.startswith(DISCLAIMER)

    @pytest.mark.parametrize("name", list(EXPECTED_OVERALL))
    def test_each_demo_astronaut_name_and_overall_status_appear(self, name: str) -> None:
        # Arrange
        record = _record_by_name(name)

        # Act
        output = render_astronaut(record, _demo_assessment(record), use_color=False)

        # Assert
        assert name in output
        assert f"overall: {EXPECTED_OVERALL[name].name}" in output

    @pytest.mark.parametrize("name", list(EXPECTED_OVERALL))
    def test_each_recommendation_action_and_rule_ids_appear(self, name: str) -> None:
        # Arrange
        record = _record_by_name(name)
        assessment = _demo_assessment(record)

        # Act
        output = render_astronaut(record, assessment, use_color=False)

        # Assert
        for recommendation in assessment.recommendations:
            assert recommendation.action in output
            for rule_id in recommendation.rule_ids:
                assert rule_id in output

    def test_all_fourteen_characteristic_labels_and_units_appear(self) -> None:
        # Arrange
        record = _record_by_name("Vega Lyra")

        # Act
        output = render_astronaut(record, _demo_assessment(record), use_color=False)

        # Assert
        assert len(CHARACTERISTIC_DEFINITIONS) == 14
        for definition in CHARACTERISTIC_DEFINITIONS:
            assert definition.characteristic.value in output
            assert definition.unit in output

    def test_missing_values_render_as_dash_with_unknown_status(self) -> None:
        # Arrange
        record = _record_by_name("Pavo Rigel")

        # Act
        output = render_astronaut(record, _demo_assessment(record), use_color=False)

        # Assert
        glucose_row = next(
            line for line in output.splitlines() if line.startswith("| Blood glucose")
        )
        assert re.search(r"\|\s+-\s+\|", glucose_row)
        assert "UNKNOWN" in glucose_row

    def test_measure_this_section_lists_missing_inputs(self) -> None:
        # Arrange
        record = _record_by_name("Pavo Rigel")

        # Act
        output = render_astronaut(record, _demo_assessment(record), use_color=False)

        # Assert
        measure_section = output.split("Measure this", 1)[1]
        for label in (
            "Blood glucose",
            "Body fat percentage",
            "Stress level",
            "Mission radiation exposure level",
            "Bone density (calcium)",
        ):
            assert f"  - {label}" in measure_section

    def test_render_functions_return_str(self) -> None:
        # Arrange
        record = _record_by_name("Kai Orion")
        assessment = _demo_assessment(record)

        # Act
        block = render_astronaut(record, assessment, use_color=False)
        report = render_report((record,), None, use_color=False)

        # Assert
        assert isinstance(block, str)
        assert isinstance(report, str)

    def test_phase_override_is_shown_in_header(self) -> None:
        # Arrange / Act
        output = render_report(
            (_record_by_name("Vega Lyra"),), MissionPhase.RETURN, use_color=False
        )

        # Assert
        assert "phase: return" in output


# --- Rendering with colour ----------------------------------------------------------------


class TestRenderWithColor:
    def test_colorize_wraps_text_with_status_code_and_reset(self) -> None:
        # Arrange / Act
        result = colorize("URGENT", Status.URGENT, use_color=True)

        # Assert
        assert result.startswith("\x1b[")
        assert result.endswith(ANSI_RESET)
        assert "URGENT" in result

    def test_colorize_returns_plain_text_when_color_disabled(self) -> None:
        # Arrange / Act
        result = colorize("OK", Status.OK, use_color=False)

        # Assert
        assert result == "OK"

    def test_colored_report_contains_ansi_codes_and_reset(self) -> None:
        # Arrange / Act
        output = render_report(DEMO_ASTRONAUTS, None, use_color=True)

        # Assert
        assert "\x1b[" in output
        assert ANSI_RESET in output


# --- Colour decision ----------------------------------------------------------------------


class TestShouldUseColor:
    def test_no_color_flag_disables_color_even_on_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.delenv("NO_COLOR", raising=False)

        # Act
        result = should_use_color(no_color=True, stream=FakeTTY())

        # Assert
        assert result is False

    def test_no_color_environment_variable_disables_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.setenv("NO_COLOR", "1")

        # Act
        result = should_use_color(no_color=False, stream=FakeTTY())

        # Assert
        assert result is False

    def test_non_tty_stream_disables_color(
        self, no_no_color_env: None
    ) -> None:
        # Arrange
        stream = io.StringIO()

        # Act
        result = should_use_color(no_color=False, stream=stream)

        # Assert
        assert result is False

    def test_tty_stream_without_flags_enables_color(self, no_no_color_env: None) -> None:
        # Arrange / Act
        result = should_use_color(no_color=False, stream=FakeTTY())

        # Assert
        assert result is True


# --- CLI parsing --------------------------------------------------------------------------


class TestParseArgs:
    def test_demo_flag_is_parsed(self) -> None:
        # Arrange / Act
        args = parse_args(["--demo"])

        # Assert
        assert args.demo is True

    def test_no_color_flag_is_parsed(self) -> None:
        # Arrange / Act
        args = parse_args(["--no-color"])

        # Assert
        assert args.no_color is True

    def test_phase_flag_is_parsed_as_phase_value(self) -> None:
        # Arrange / Act
        args = parse_args(["--phase", "return"])

        # Assert
        assert args.phase == "return"
        assert MissionPhase(args.phase) is MissionPhase.RETURN

    def test_invalid_phase_exits_with_system_exit(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SystemExit):
            parse_args(["--phase", "not-a-phase"])

    def test_astronaut_filter_is_parsed(self) -> None:
        # Arrange / Act
        args = parse_args(["--astronaut", "Kai Orion"])

        # Assert
        assert args.astronaut == "Kai Orion"

    def test_db_path_is_parsed_as_path(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "custom.db"

        # Act
        args = parse_args(["--db", str(target)])

        # Assert
        assert args.db == target
        assert isinstance(args.db, Path)

    def test_defaults_when_no_arguments(self) -> None:
        # Arrange / Act
        args = parse_args([])

        # Assert
        assert args.demo is False
        assert args.no_color is False
        assert args.phase is None
        assert args.astronaut is None
        assert args.db == dashboard_terminal.DB_PATH


# --- Demo data ----------------------------------------------------------------------------


class TestDemoData:
    def test_at_least_four_demo_astronauts_exist(self) -> None:
        # Arrange / Act / Assert
        assert len(DEMO_ASTRONAUTS) >= 4

    def test_overall_statuses_cover_ok_watch_action_and_urgent(self) -> None:
        # Arrange
        statuses = {_demo_assessment(record).overall for record in DEMO_ASTRONAUTS}

        # Act / Assert
        assert {Status.OK, Status.WATCH, Status.ACTION, Status.URGENT} <= statuses

    @pytest.mark.parametrize("name", list(EXPECTED_OVERALL))
    def test_each_demo_astronaut_has_expected_overall_status(self, name: str) -> None:
        # Arrange
        record = _record_by_name(name)

        # Act
        overall = _demo_assessment(record).overall

        # Assert
        assert overall is EXPECTED_OVERALL[name]

    def test_demo_values_are_read_only(self) -> None:
        # Arrange
        values = DEMO_ASTRONAUTS[0].values

        # Act / Assert
        assert isinstance(values, MappingProxyType)
        with pytest.raises(TypeError):
            values[C.AGE] = 99  # type: ignore[index]

    def test_demo_record_is_frozen(self) -> None:
        # Arrange
        record = DEMO_ASTRONAUTS[0]

        # Act / Assert
        with pytest.raises(AttributeError):
            record.note = "changed"  # type: ignore[misc]

    def test_present_core_values_are_within_definition_limits(self) -> None:
        # Arrange
        limits = {d.characteristic: d for d in CHARACTERISTIC_DEFINITIONS}

        # Act / Assert
        for record in DEMO_ASTRONAUTS:
            for key, value in record.values.items():
                if isinstance(key, C) and value is not None:
                    definition = limits[key]
                    assert definition.minimum <= value <= definition.maximum, (
                        f"{_name(record)}: {key.value}={value}"
                    )


# --- Read-only database loading -----------------------------------------------------------


class TestLoadDbAstronauts:
    def test_loads_saved_astronaut_with_values(self, tmp_path: Path) -> None:
        # Arrange
        db = _make_db(tmp_path)

        # Act
        records = load_db_astronauts(db)

        # Assert
        assert len(records) == 1
        assert records[0].last_name == "Test"
        assert records[0].first_name == "Ana"
        for characteristic, expected in HEALTHY_CORE.items():
            assert records[0].values[characteristic] == expected

    def test_database_file_bytes_are_unchanged_after_load(self, tmp_path: Path) -> None:
        # Arrange
        db = _make_db(tmp_path)
        before = db.read_bytes()

        # Act
        load_db_astronauts(db)

        # Assert
        assert db.read_bytes() == before

    def test_connection_is_opened_with_read_only_uri(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        db = _make_db(tmp_path)
        real_connect = sqlite3.connect
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def recording_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
            calls.append((args, kwargs))
            return real_connect(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(dashboard_terminal.sqlite3, "connect", recording_connect)

        # Act
        load_db_astronauts(db)

        # Assert
        assert len(calls) == 1
        uri = calls[0][0][0]
        assert isinstance(uri, str)
        assert uri.startswith("file:")
        assert "mode=ro" in uri
        assert calls[0][1].get("uri") is True

    def test_read_only_connection_rejects_writes(self, tmp_path: Path) -> None:
        # Arrange
        db = _make_db(tmp_path)
        uri = db.resolve().as_uri() + "?mode=ro"

        # Act / Assert
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("DELETE FROM astronauti")

    def test_missing_database_is_not_created(self, tmp_path: Path) -> None:
        # Arrange
        missing = tmp_path / "does_not_exist.db"

        # Act / Assert
        with pytest.raises(sqlite3.OperationalError):
            load_db_astronauts(missing)
        assert not missing.exists()

    def test_old_style_table_yields_none_for_all_characteristics(self, tmp_path: Path) -> None:
        # Arrange
        db = _make_old_style_db(tmp_path)

        # Act
        records = load_db_astronauts(db)

        # Assert
        assert len(records) == 1
        assert (records[0].last_name, records[0].first_name) == ("Old", "Row")
        assert len(records[0].values) == 14
        assert all(value is None for value in records[0].values.values())


# --- main() -------------------------------------------------------------------------------


class TestMain:
    def test_demo_no_color_returns_zero_and_prints_all_names(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange / Act
        exit_code = main(["--demo", "--no-color"])

        # Assert
        output = capsys.readouterr().out
        assert exit_code == 0
        assert "\x1b[" not in output
        for record in DEMO_ASTRONAUTS:
            assert _name(record) in output

    def test_astronaut_filter_is_case_insensitive_and_shows_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange / Act
        exit_code = main(["--demo", "--no-color", "--astronaut", "kai ORION"])

        # Assert
        output = capsys.readouterr().out
        assert exit_code == 0
        assert "Kai Orion" in output
        assert "Vega Lyra" not in output
        assert "Draco Altair" not in output

    def test_unknown_astronaut_returns_one(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Arrange / Act
        exit_code = main(["--demo", "--no-color", "--astronaut", "Nobody Here"])

        # Assert
        assert exit_code == 1
        assert "No astronaut matched" in capsys.readouterr().out

    def test_nonexistent_db_returns_one_and_creates_no_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange
        missing = tmp_path / "absent.db"

        # Act
        exit_code = main(["--db", str(missing), "--no-color"])

        # Assert
        assert exit_code == 1
        assert not missing.exists()
        assert "Database not found" in capsys.readouterr().out

    def test_phase_flag_is_shown_in_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Arrange / Act
        exit_code = main(["--demo", "--no-color", "--phase", "return"])

        # Assert
        assert exit_code == 0
        assert "phase: return" in capsys.readouterr().out

    def test_db_with_real_astronaut_renders_and_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange
        db = _make_db(tmp_path)
        before = db.read_bytes()

        # Act
        exit_code = main(["--db", str(db), "--no-color"])

        # Assert
        output = capsys.readouterr().out
        assert exit_code == 0
        assert "Test Ana" in output
        assert db.read_bytes() == before

    def test_old_style_db_renders_unknown_and_measure_this(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange
        db = _make_old_style_db(tmp_path)

        # Act
        exit_code = main(["--db", str(db), "--no-color"])

        # Assert
        output = capsys.readouterr().out
        assert exit_code == 0
        assert "UNKNOWN" in output
        assert "Measure this" in output


def test_should_use_color_ignores_empty_no_color_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    class FakeTty(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setenv("NO_COLOR", "")

    # Act
    result = should_use_color(False, FakeTty())

    # Assert
    assert result is True
