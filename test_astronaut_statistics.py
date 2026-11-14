import sys

from astronaut_statistics import main
from test_historic import make_db


def test_prints_a_summary_for_every_astronaut(tmp_path, capsys):
    # Arrange
    db = make_db(tmp_path / "s.db", [60, 66])

    # Act
    code = main(["--db", str(db)])

    # Assert
    out = capsys.readouterr().out
    assert code == 0
    assert "Doe Jane: 2 measurement(s)" in out
    assert "Nobody Empty: 0 measurement(s)" in out
    assert "Average heart rate (bpm): n=2 min=60 max=66 mean=63.00" in out


def test_missing_database_is_reported_not_created(tmp_path, capsys):
    # Arrange
    missing = tmp_path / "none.db"

    # Act
    code = main(["--db", str(missing)])

    # Assert
    assert code == 1
    assert "not found" in capsys.readouterr().out
    assert not missing.exists()


def test_plot_without_plotly_gives_a_clear_message(tmp_path, capsys, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "s.db", [60])
    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.express", None)

    # Act
    code = main(["--plot", "--db", str(db)])

    # Assert
    assert code == 1
    assert "pip install plotly" in capsys.readouterr().out
