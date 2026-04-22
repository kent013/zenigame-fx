"""Tests for scripts/oanda_cfd_probe.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from scripts.oanda_cfd_probe import DEFAULT_INSTRUMENTS, main

BASE_URL = "https://api-fxtrade.oanda.com"
TEST_INSTRUMENTS = ("SPX500_USD", "WTICO_USD", "XAU_USD")


@pytest.fixture(autouse=True)
def _set_oanda_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """OandaClient は account_id / token を要求するためダミー値を設定。

    `Settings` (BaseSettings) は run_probe 内で都度 instantiate される実装のため、
    monkeypatch.setenv が反映される。
    """
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "001-009-12345-001")
    monkeypatch.setenv("OANDA_API_TOKEN", "dummy-token")


def _candles_response(instrument: str, n: int = 10) -> dict:
    """OANDA 公式 candles レスポンス形状に準拠した mock payload。"""
    return {
        "instrument": instrument,
        "granularity": "M1",
        "candles": [
            {
                "time": f"2026-04-22T0{i}:00:00.000000000Z",
                "volume": 100 + i,
                "complete": True,
                "bid": {"o": "1.0", "h": "1.1", "l": "0.9", "c": "1.05"},
                "ask": {"o": "1.0", "h": "1.1", "l": "0.9", "c": "1.06"},
            }
            for i in range(min(n, 10))
        ],
    }


def _err_response(message: str) -> dict:
    """OANDA エラーレスポンス形状: {"errorMessage": "..."}"""
    return {"errorMessage": message}


def _run_main(
    tmp_path: Path, instruments: tuple[str, ...] = TEST_INSTRUMENTS
) -> tuple[int, Path, Path]:
    out_json = tmp_path / "probe-result.json"
    out_md = tmp_path / "probe-report.md"
    code = main(
        [
            "--instruments",
            *instruments,
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
            "--base-url",
            BASE_URL,
        ]
    )
    return code, out_json, out_md


@respx.mock
def test_all_ok_marks_each_instrument_as_ok(tmp_path: Path) -> None:
    for inst in TEST_INSTRUMENTS:
        respx.get(f"{BASE_URL}/v3/instruments/{inst}/candles").mock(
            return_value=Response(200, json=_candles_response(inst))
        )
    code, out_json, out_md = _run_main(tmp_path)
    assert code == 0
    payload = json.loads(out_json.read_text())
    assert payload["summary"]["ok"] == len(TEST_INSTRUMENTS)
    assert all(r["verdict"] == "OK" for r in payload["results"])
    assert all(r["candle_count"] == 10 for r in payload["results"])
    assert all(r["first_candle_time"] is not None for r in payload["results"])
    assert "全 OK" in out_md.read_text()


@respx.mock
def test_all_forbidden_marks_each_instrument_as_forbidden(tmp_path: Path) -> None:
    for inst in TEST_INSTRUMENTS:
        respx.get(f"{BASE_URL}/v3/instruments/{inst}/candles").mock(
            return_value=Response(403, json=_err_response("insufficient permissions"))
        )
    code, out_json, out_md = _run_main(tmp_path)
    assert code == 0
    payload = json.loads(out_json.read_text())
    assert payload["summary"]["forbidden"] == len(TEST_INSTRUMENTS)
    assert all(r["verdict"] == "FORBIDDEN" for r in payload["results"])
    assert all(r["status_code"] == 403 for r in payload["results"])
    assert "全不可" in out_md.read_text()


@respx.mock
def test_all_not_found_marks_each_instrument_as_not_found(tmp_path: Path) -> None:
    for inst in TEST_INSTRUMENTS:
        respx.get(f"{BASE_URL}/v3/instruments/{inst}/candles").mock(
            return_value=Response(404, json=_err_response("unknown instrument"))
        )
    code, out_json, _ = _run_main(tmp_path)
    assert code == 0
    payload = json.loads(out_json.read_text())
    assert payload["summary"]["not_found"] == len(TEST_INSTRUMENTS)
    assert all(r["status_code"] == 404 for r in payload["results"])


@respx.mock
def test_mixed_responses_independently_set_verdict_per_instrument(tmp_path: Path) -> None:
    respx.get(f"{BASE_URL}/v3/instruments/SPX500_USD/candles").mock(
        return_value=Response(200, json=_candles_response("SPX500_USD"))
    )
    respx.get(f"{BASE_URL}/v3/instruments/WTICO_USD/candles").mock(
        return_value=Response(403, json=_err_response("forbidden"))
    )
    respx.get(f"{BASE_URL}/v3/instruments/XAU_USD/candles").mock(
        return_value=Response(404, json=_err_response("not found"))
    )
    code, out_json, out_md = _run_main(tmp_path)
    assert code == 0
    payload = json.loads(out_json.read_text())
    summary = payload["summary"]
    assert summary["ok"] == 1 and summary["forbidden"] == 1 and summary["not_found"] == 1
    by_inst = {r["instrument"]: r for r in payload["results"]}
    assert by_inst["SPX500_USD"]["verdict"] == "OK"
    assert by_inst["WTICO_USD"]["verdict"] == "FORBIDDEN"
    assert by_inst["XAU_USD"]["verdict"] == "NOT_FOUND"
    assert "部分 OK" in out_md.read_text()


@respx.mock
def test_auth_error_at_first_instrument_aborts_with_exit_code_1(tmp_path: Path) -> None:
    """1 件目で 401 が返ったら即 abort する。"""
    respx.get(f"{BASE_URL}/v3/instruments/SPX500_USD/candles").mock(
        return_value=Response(401, json=_err_response("unauthorized"))
    )
    code, out_json, out_md = _run_main(tmp_path, instruments=("SPX500_USD",))
    assert code == 1
    assert not out_json.exists()
    assert not out_md.exists()


@respx.mock
def test_auth_error_mid_run_aborts_and_skips_remaining_instruments(tmp_path: Path) -> None:
    """1 件目 OK・2 件目 401・3 件目 未試行 を担保する。"""
    spx_route = respx.get(f"{BASE_URL}/v3/instruments/SPX500_USD/candles").mock(
        return_value=Response(200, json=_candles_response("SPX500_USD"))
    )
    wti_route = respx.get(f"{BASE_URL}/v3/instruments/WTICO_USD/candles").mock(
        return_value=Response(401, json=_err_response("token revoked"))
    )
    xau_route = respx.get(f"{BASE_URL}/v3/instruments/XAU_USD/candles").mock(
        return_value=Response(200, json=_candles_response("XAU_USD"))
    )
    code, out_json, out_md = _run_main(
        tmp_path, instruments=("SPX500_USD", "WTICO_USD", "XAU_USD")
    )
    assert code == 1
    assert not out_json.exists()
    assert not out_md.exists()
    assert spx_route.called
    assert wti_route.called
    assert not xau_route.called


@respx.mock
def test_server_error_after_retry_is_classified_as_other(tmp_path: Path) -> None:
    """500 が tenacity retry 後も継続したら verdict=OTHER で記録（abort しない）。"""
    respx.get(f"{BASE_URL}/v3/instruments/SPX500_USD/candles").mock(
        return_value=Response(500, text="internal server error")
    )
    code, out_json, _ = _run_main(tmp_path, instruments=("SPX500_USD",))
    assert code == 0
    payload = json.loads(out_json.read_text())
    assert payload["summary"]["other"] == 1
    assert payload["summary"]["ok"] == 0
    result = payload["results"][0]
    assert result["verdict"] == "OTHER"
    # 既存 OandaClient は 5xx を OandaServerError として raise → status_code は記録できない
    assert result["status_code"] is None
    assert "OandaServerError" in (result["error_message"] or "") or "500" in (result["error_message"] or "")


@respx.mock
def test_unknown_4xx_status_is_classified_as_other(tmp_path: Path) -> None:
    """422 等 401/403/404 以外の 4xx は verdict=OTHER で記録（status_code 保持）。"""
    respx.get(f"{BASE_URL}/v3/instruments/SPX500_USD/candles").mock(
        return_value=Response(422, json=_err_response("unprocessable entity"))
    )
    code, out_json, _ = _run_main(tmp_path, instruments=("SPX500_USD",))
    assert code == 0
    payload = json.loads(out_json.read_text())
    assert payload["summary"]["other"] == 1
    result = payload["results"][0]
    assert result["verdict"] == "OTHER"
    assert result["status_code"] == 422


def test_default_instruments_cover_all_seven_targets() -> None:
    """定数 DEFAULT_INSTRUMENTS が設計通り 7 件であることを担保。"""
    assert set(DEFAULT_INSTRUMENTS) == {
        "SPX500_USD",
        "WTICO_USD",
        "XAU_USD",
        "XCU_USD",
        "JP225_USD",
        "USB10Y_USD",
        "USB02Y_USD",
    }
