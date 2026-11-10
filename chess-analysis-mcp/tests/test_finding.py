"""Tests for coach.finding (Phase 1 of the grounded-explanations roadmap)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

from coach.finding import MAX_LOSS_PAWNS, Finding, finding_id, from_blunder  # noqa: E402
from data.models import BlunderInfo  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _blunder(**overrides) -> BlunderInfo:
    base = dict(
        move_number=1,
        ply=1,
        color="white",
        played_move="f2f3",
        best_move="e2e4",
        played_cp=-60,
        best_cp=30,
        cp_loss=90,
        fen_before=START,
        fen_after="rnbqkbnr/pppppppp/8/8/8/5P2/PPPPP1PP/RNBQKBNR b KQkq - 0 1",
        classification="inaccuracy",
    )
    base.update(overrides)
    return BlunderInfo(**base)


def _finding(**overrides) -> Finding:
    return from_blunder(_blunder(**overrides), game_id="g1", engine_version="sf-test", depth=18)


def test_loss_is_in_pawns():
    assert _finding().loss == pytest.approx(0.9)


def test_san_is_derived_from_fen():
    f = _finding()
    assert (f.played_san, f.best_san) == ("f3", "e4")


def test_illegal_move_raises():
    with pytest.raises(ValueError, match="not legal"):
        _finding(best_move="e2e5")


def test_negative_cp_loss_becomes_zero():
    f = _finding(cp_loss=-40)
    assert f.loss == 0.0 and f.classification == "ok"


def test_negative_loss_rejected_on_direct_construction():
    with pytest.raises(ValueError, match="loss"):
        Finding(**{**_finding().__dict__, "loss": -0.1})


@pytest.mark.parametrize(
    "cp_loss, label",
    [(49, "ok"), (50, "inaccuracy"), (100, "mistake"), (200, "blunder")],
)
def test_classification_follows_analyzer_thresholds(cp_loss, label):
    assert _finding(cp_loss=cp_loss).classification == label


def test_classification_ignores_stale_label_on_input():
    assert _finding(cp_loss=250, classification="inaccuracy").classification == "blunder"


def test_mate_loss_is_capped_and_flagged():
    f = _finding(best_cp=30_000, played_cp=-100, cp_loss=30_100)
    assert f.mate_involved and f.loss == MAX_LOSS_PAWNS


def test_id_is_stable():
    assert _finding().id == finding_id("g1", 1) == "g1:ply1"


def test_json_round_trip():
    f = _finding()
    assert Finding.from_json(f.to_json()) == f


def test_pv_defaults_to_best_move():
    assert _finding().pv == ["e2e4"]
