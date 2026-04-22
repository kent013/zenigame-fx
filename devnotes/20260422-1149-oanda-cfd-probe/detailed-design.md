# Detailed Design: OANDA CFD Instrument Probe (T005)

[概念設計](conceptual-design.md) の APPROVED 版を踏まえた実装詳細。

## 1. ファイル一覧

| 種別 | パス | 操作 |
|---|---|---|
| 新規 | `scripts/oanda_cfd_probe.py` | probe 本体 |
| 新規 | `tests/scripts/__init__.py` | パッケージマーカー（空） |
| 新規 | `tests/scripts/test_oanda_cfd_probe.py` | respx mock テスト |
| 更新 | `docs/alpha_factory/runbook.md` | OANDA CFD 取得手順を追記 |
| 更新 | `docs/alpha_factory/cross-pair.md` | external data 戦略を実測結果で更新 |
| 出力 | `devnotes/20260422-1149-oanda-cfd-probe/probe-result.json` | 実 API 走行結果 (CI 不要、devnotes に commit) |
| 出力 | `devnotes/20260422-1149-oanda-cfd-probe/probe-report.md` | サマリレポート |

`src/` 以下は **変更なし**。 `OandaClient` 既存実装をそのまま再利用する。

## 2. `scripts/oanda_cfd_probe.py` 詳細

### 2.1 モジュールレイアウト

```python
"""OANDA CFD instrument 疎通試験 (T005).

7 件の CFD 系 instrument に candles エンドポイントを試行し、
verdict (OK / FORBIDDEN / NOT_FOUND / OTHER) を判定する。
DB 書き込みは行わない。結果は JSON と Markdown レポートに出力。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import structlog

from src.api.oanda.client import OandaAuthError, OandaClient
from src.config import settings

logger = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "devnotes" / "20260422-1149-oanda-cfd-probe"
DEFAULT_INSTRUMENTS = (
    "SPX500_USD",
    "WTICO_USD",
    "XAU_USD",
    "XCU_USD",
    "JP225_USD",
    "USB10Y_USD",
    "USB02Y_USD",
)

Verdict = Literal["OK", "FORBIDDEN", "NOT_FOUND", "OTHER"]
```

### 2.2 データクラス

```python
@dataclass
class ProbeResult:
    instrument: str
    status_code: int | None
    verdict: Verdict
    candle_count: int | None
    first_candle_time: str | None
    error_message: str | None


@dataclass
class ProbeSummary:
    total: int
    ok: int
    forbidden: int
    not_found: int
    other: int

    @classmethod
    def from_results(cls, results: list[ProbeResult]) -> "ProbeSummary":
        return cls(
            total=len(results),
            ok=sum(1 for r in results if r.verdict == "OK"),
            forbidden=sum(1 for r in results if r.verdict == "FORBIDDEN"),
            not_found=sum(1 for r in results if r.verdict == "NOT_FOUND"),
            other=sum(1 for r in results if r.verdict == "OTHER"),
        )
```

### 2.3 単一 instrument の probe

**仕様（OandaClient 実装契約に依存しない）**:

| status | verdict | abort? |
|---|---|---|
| 200 | OK | no |
| 401 | (fatal) | **yes** — `OandaAuthError` へ変換して caller へ raise |
| 403 | FORBIDDEN | no |
| 404 | NOT_FOUND | no |
| 5xx (retry 失敗後) / 429 / TransportError / その他 | OTHER | no |

```python
def probe_one(client: OandaClient, instrument: str) -> ProbeResult:
    try:
        resp = client.get_candles(instrument, granularity="M1", price="BA", count=10)
    except OandaAuthError:
        # 既存 client が 401 を OandaAuthError に変換する場合 → そのまま caller へ
        raise
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 401:
            # 万一 client 実装が将来変わって 401 が HTTPStatusError として降ってきても
            # 必ず fatal 扱いにする。OandaAuthError へ変換して caller へ raise。
            raise OandaAuthError(f"401 Unauthorized: {exc.response.text[:200]}") from exc
        verdict: Verdict
        if status_code == 403:
            verdict = "FORBIDDEN"
        elif status_code == 404:
            verdict = "NOT_FOUND"
        else:
            verdict = "OTHER"
        return ProbeResult(
            instrument=instrument,
            status_code=status_code,
            verdict=verdict,
            candle_count=None,
            first_candle_time=None,
            error_message=exc.response.text[:500],
        )
    except Exception as exc:  # 5xx retry 失敗 / TransportError / その他
        return ProbeResult(
            instrument=instrument,
            status_code=None,
            verdict="OTHER",
            candle_count=None,
            first_candle_time=None,
            error_message=f"{type(exc).__name__}: {exc}"[:500],
        )
    first_time = resp.candles[0].time.isoformat() if resp.candles else None
    return ProbeResult(
        instrument=instrument,
        status_code=200,
        verdict="OK",
        candle_count=len(resp.candles),
        first_candle_time=first_time,
        error_message=None,
    )
```

**注**: 既存 `OandaClient._get` 内の `_raise_for_status` で 401 は `OandaAuthError`、403/404 は `raise_for_status()` 経由で `httpx.HTTPStatusError` が raise される（実装契約）。本 probe では **両経路で 401 を fatal にできる二重防御** を採る。これにより 401 fatal 仕様が `OandaClient` 内部実装の変更に対して堅牢になる。

### 2.4 メイン処理

**設計方針: `settings` を import 時に固定参照しない**

理由: `Settings` (BaseSettings) は import 時にインスタンス化されるため、テストで `monkeypatch.setenv` を使っても `settings.oanda_*` は古い値のまま。`run_probe` 呼び出し時に `Settings()` を再評価することで test と本番を両立する。

```python
def _resolve_runtime_settings(
    base_url: str | None,
    account_id: str | None,
    token: str | None,
) -> tuple[str, str, str]:
    """run-time に Settings を再評価（test の env override が反映されるよう）。

    全 3 引数が CLI で与えられている場合は Settings を一切参照しない。
    これにより Settings 側に将来必須フィールドが追加されても CLI override が
    最優先で動作する（壊れにくさ優先）。
    """
    if base_url is not None and account_id is not None and token is not None:
        return base_url, account_id, token
    # 部分的にしか CLI 指定がない場合のみ Settings を遅延 instantiate
    from src.config import Settings
    s = Settings()
    return (
        base_url or s.oanda_base_url,
        account_id or s.oanda_account_id,
        token or s.oanda_api_token,
    )


def run_probe(
    instruments: tuple[str, ...],
    output_json: Path,
    output_md: Path,
    base_url: str | None = None,
    account_id: str | None = None,
    token: str | None = None,
) -> int:
    """Probe を実行し JSON + Markdown を出力。401 検知時は exit 1。

    出力はトランザクション的に扱う: 401 abort 時は JSON/MD ともに書き出さない。
    """
    probed_at = datetime.now(tz=UTC)
    results: list[ProbeResult] = []
    actual_base_url, actual_account_id, actual_token = _resolve_runtime_settings(
        base_url, account_id, token
    )

    try:
        with OandaClient(
            base_url=actual_base_url,
            account_id=actual_account_id,
            token=actual_token,
        ) as client:
            for name in instruments:
                logger.info("probe.request", instrument=name)
                result = probe_one(client, name)
                logger.info(
                    "probe.result",
                    instrument=name,
                    verdict=result.verdict,
                    status=result.status_code,
                    candles=result.candle_count,
                )
                results.append(result)
                _print_stdout(result)
    except OandaAuthError as exc:
        print(f"[fatal] OANDA 401 Unauthorized: {exc}", file=sys.stderr)
        print("[fatal] OANDA_API_TOKEN を確認してください (.env)", file=sys.stderr)
        return 1

    summary = ProbeSummary.from_results(results)
    _write_json(output_json, probed_at, actual_base_url, results, summary)
    _write_markdown(output_md, probed_at, actual_base_url, results, summary)
    print(f"[done] JSON: {output_json}")
    print(f"[done] Markdown: {output_md}")
    return 0


def _print_stdout(result: ProbeResult) -> None:
    extra = ""
    if result.candle_count is not None:
        extra = f" candles={result.candle_count}"
    if result.error_message:
        extra += f" err={result.error_message[:80]}"
    status = result.status_code if result.status_code is not None else "—"
    print(f"[{result.verdict:9s}] {result.instrument:12s} status={status}{extra}")


def _write_json(
    path: Path,
    probed_at: datetime,
    base_url: str,
    results: list[ProbeResult],
    summary: ProbeSummary,
) -> None:
    """JSON 出力。dataclass 内の値は str/int/None のみで型を閉じる。

    `probed_at` は明示的に isoformat 文字列に正規化してから dict に入れる
    （json.dumps デフォルトの `default=` に頼らない）。
    """
    payload = {
        "probed_at": probed_at.isoformat(),  # str
        "base_url": base_url,
        "results": [asdict(r) for r in results],  # ProbeResult の field は str/int/None のみ
        "summary": asdict(summary),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(
    path: Path,
    probed_at: datetime,
    base_url: str,
    results: list[ProbeResult],
    summary: ProbeSummary,
) -> None:
    lines: list[str] = []
    lines.append("# OANDA CFD Instrument Probe Report (T005)")
    lines.append("")
    lines.append("## 試験条件")
    lines.append(f"- 試験日時 (UTC): {probed_at.isoformat()}")
    lines.append(f"- base_url: {base_url}")
    lines.append(f"- granularity: M1, price: BA, count: 10")
    lines.append("")
    lines.append("## 結果サマリー")
    lines.append("")
    lines.append("| Instrument | verdict | status | candle_count | first_candle_time | error |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        err = (r.error_message or "")[:60]
        lines.append(
            f"| {r.instrument} | {r.verdict} | {r.status_code if r.status_code else '—'} | "
            f"{r.candle_count if r.candle_count is not None else '—'} | "
            f"{r.first_candle_time or '—'} | {err} |"
        )
    lines.append("")
    lines.append("## 集計")
    lines.append(f"- total: {summary.total}")
    lines.append(f"- OK: {summary.ok}")
    lines.append(f"- FORBIDDEN: {summary.forbidden}")
    lines.append(f"- NOT_FOUND: {summary.not_found}")
    lines.append(f"- OTHER: {summary.other}")
    lines.append("")
    lines.append("## 判定")
    if summary.ok == summary.total:
        verdict_overall = "全 OK"
    elif summary.ok == 0:
        verdict_overall = "全不可"
    else:
        verdict_overall = f"部分 OK ({summary.ok}/{summary.total})"
    lines.append(f"- {verdict_overall}")
    lines.append("")
    lines.append("## 次アクション提案")
    if summary.ok == summary.total:
        lines.append("- 全 instrument が OK。OANDA CFD ingest pipeline 拡張 TODO を別途起票し、FX と同じ M1 取得経路で取り込み実装へ進む。")
    elif summary.ok == 0:
        lines.append("- いずれの CFD instrument も取得不可。FRED + 自前計算 (realized_vol / usd_strength_synthetic) 強化で primitive を代替。")
    else:
        lines.append("- 部分的に取得可。OK 分は OANDA ingest TODO、不可分は FRED 代替 / FX データ完結 (realized_vol 等) primitive TODO の 2 本立てで進む。")
    lines.append("")
    lines.append("## 観測 vs 解釈の分離（注記）")
    lines.append("- verdict は観測事実のみを記録。FORBIDDEN / NOT_FOUND は **現 live/account/environment で当該 instrument の candles を取得できなかった** という事実に過ぎず、「永久に使えない」「OANDA に存在しない」と解釈してはならない。")
    lines.append("- account 区分・契約状態・地域規制等によって挙動が変わる可能性がある。代替経路を検討する際の入力情報として扱うこと。")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe OANDA CFD instruments via candles endpoint")
    parser.add_argument("--instruments", nargs="+", default=list(DEFAULT_INSTRUMENTS))
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_DIR / "probe-result.json")
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_DIR / "probe-report.md")
    parser.add_argument("--base-url", default=None, help="Override OANDA base_url (e.g. for testing)")
    parser.add_argument("--account-id", default=None, help="Override OANDA account id")
    parser.add_argument("--token", default=None, help="Override OANDA API token (avoid CLI; prefer .env)")
    args = parser.parse_args(argv)
    return run_probe(
        instruments=tuple(args.instruments),
        output_json=args.output_json,
        output_md=args.output_md,
        base_url=args.base_url,
        account_id=args.account_id,
        token=args.token,
    )


if __name__ == "__main__":
    sys.exit(main())
```

### 2.5 設計上の注意点

- **`OandaAuthError` は `Exception` の前で捕捉する** — `Exception` で先に捕まえてしまうと 401 と他のエラーを区別できなくなる。
- **`httpx.HTTPStatusError` も `Exception` の前で捕捉する** — `OandaError` のサブクラスではないので順序を間違えない。
- **`response.text[:500]`** で error_message を切り詰める — 大きい body が JSON にダンプされて読みにくくなるのを防ぐ。
- **`first_candle_time`** は `Candle.time` (datetime) を `isoformat()` する。`OandaClient` モデルは pydantic で datetime parse 済み。

## 3. テスト詳細

### 3.1 ファイル構成

`tests/scripts/__init__.py`: 空ファイル
`tests/scripts/test_oanda_cfd_probe.py`: respx mock + tmp_path fixture

### 3.2 テストケース

mock の OANDA 応答形状は実 API ドキュメントおよび `tests/fixtures/oanda/candles_usdjpy_m1.json` (既存) の形状に合わせる:
- 200: `{"instrument", "granularity", "candles": [{"time", "volume", "complete", "bid": {o,h,l,c}, "ask": {o,h,l,c}}, ...]}`
- 401/403/404: OANDA は `{"errorMessage": "..."}` の JSON を返す（公式 docs 参照）

```python
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

    `Settings` (BaseSettings) は run_probe 内で再評価される実装のため、
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


def _run_main(tmp_path: Path, instruments=TEST_INSTRUMENTS) -> tuple[int, Path, Path]:
    out_json = tmp_path / "probe-result.json"
    out_md = tmp_path / "probe-report.md"
    code = main(
        [
            "--instruments", *instruments,
            "--output-json", str(out_json),
            "--output-md", str(out_md),
            "--base-url", BASE_URL,
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
    code, out_json, out_md = _run_main(tmp_path, instruments=("SPX500_USD", "WTICO_USD", "XAU_USD"))
    assert code == 1
    assert not out_json.exists()
    assert not out_md.exists()
    # SPX500 と WTICO は呼ばれた、XAU は呼ばれなかった
    assert spx_route.called
    assert wti_route.called
    assert not xau_route.called


def test_default_instruments_cover_all_seven_targets() -> None:
    """定数 DEFAULT_INSTRUMENTS が設計通り 7 件であることを担保。"""
    assert set(DEFAULT_INSTRUMENTS) == {
        "SPX500_USD", "WTICO_USD", "XAU_USD", "XCU_USD",
        "JP225_USD", "USB10Y_USD", "USB02Y_USD",
    }
```

### 3.3 テスト設計上の注意

- `monkeypatch.setenv` で `OANDA_ACCOUNT_ID` / `OANDA_API_TOKEN` をダミー設定 → `OandaClient` 初期化時の空文字バリデーションを通す。
- `--base-url` で test 用 URL に上書き → 実環境の base_url に依存しない。
- 401 abort 時は JSON/MD ファイルが書かれないことを assert（途中状態を残さない設計）。
- テスト名は **振る舞いを説明する汎用的な名前**（日付・session 固有 ID は入れない）。

## 4. ドキュメント更新

### 4.1 `docs/alpha_factory/runbook.md`

`### 6. FRED 取得手順` の後に新セクション `### 7. OANDA CFD instrument 疎通試験` を追加:

```markdown
### 7. OANDA CFD instrument 疎通試験

CFD 系 instrument (SPX500/WTI/XAU/XCU/JP225/USB10Y/USB02Y) が現 OANDA live 口座から candles 取得できるかを試験する。primitive P7-P12 実装の前提情報。

#### 実行

\`\`\`bash
uv run python scripts/oanda_cfd_probe.py
\`\`\`

結果は `devnotes/20260422-1149-oanda-cfd-probe/probe-result.json` (生データ) と `probe-report.md` (整形レポート) に出力。stdout には各 instrument の verdict を逐次表示。

#### Verdict 仕様

| HTTP status | verdict | スクリプト挙動 |
|---|---|---|
| 200 | OK | 結果記録、続行 |
| 401 | (fatal) | **即 abort, exit 1**, JSON/MD は書かない |
| 403 | FORBIDDEN | 結果記録、続行 |
| 404 | NOT_FOUND | 結果記録、続行 |
| 5xx (retry 失敗後) / 429 / TransportError / その他 | OTHER | 結果記録、続行 |

#### 観測 vs 解釈

verdict は観測事実のみ。FORBIDDEN/NOT_FOUND は **現 live/account/environment での観測結果** であり、永久不可とは解釈しないこと。account 区分・契約状態の変更で結果が変わる可能性あり。

#### 失敗時

| 失敗 | 対応 |
|------|------|
| Exit 1 + `[fatal] OANDA 401` | `OANDA_API_TOKEN` を `.env` で再確認 |
| 全件 OTHER (5xx / TransportError) | 時間を置いて再実行 |
```

### 4.2 `docs/alpha_factory/cross-pair.md`

末尾の `## 関連 TODO` の前に新セクションを追加（実 API 走行結果に基づき更新）:

```markdown
## External Data 戦略（CFD 取得可否ベース）

primitive P7-P12 が要求する CFD 系データ (S&P 500 / WTI / Gold / Copper / 米国債) の取得経路は OANDA CFD 疎通試験 (T005) の実測結果で確定する。

| 状態 | 戦略 |
|---|---|
| 全 OK | OANDA で M1 candles を取り込み、FX と同じ ingest パイプラインを拡張 |
| 部分 OK | OK 分は OANDA、不可分は FRED 日足代替 + FX 派生指標 (realized_vol, usd_strength_synthetic) で補完 |
| 全不可 | FRED + 自前計算 primitive 強化のみ |

実測結果: `devnotes/20260422-1149-oanda-cfd-probe/probe-report.md`
```

## 5. 実装順序

1. `scripts/oanda_cfd_probe.py` 新設
2. `tests/scripts/__init__.py` 作成（空）
3. `tests/scripts/test_oanda_cfd_probe.py` 新設
4. `uv run pytest tests/scripts/test_oanda_cfd_probe.py -v` で全 6 テスト pass 確認
5. `uv run python scripts/oanda_cfd_probe.py` で実 API 走行
6. `probe-result.json` / `probe-report.md` を確認、レポートに次アクション提案を整える
7. `runbook.md` / `cross-pair.md` を実測結果で更新
8. Codex impl-review

## 6. 受け入れチェックリスト（実装完了時）

- [ ] `scripts/oanda_cfd_probe.py` が定義通り動作（7 件 probe）
- [ ] `tests/scripts/test_oanda_cfd_probe.py` の 6 テストが全て pass
- [ ] 実 API で 1 回走行し `probe-result.json` / `probe-report.md` が devnotes に保存・commit
- [ ] `runbook.md` § 7 が追記
- [ ] `cross-pair.md` の external data 戦略セクションが追記
- [ ] Codex impl-review APPROVED
- [ ] T005 close + main merge 完了

## 7. 既存資産への影響範囲

| 既存ファイル | 影響 |
|---|---|
| `src/api/oanda/client.py` | 変更なし（読み取り専用で利用） |
| `src/config.py` | 変更なし |
| `scripts/oanda_ping.py` | 変更なし（参考実装としてのみ） |
| `tests/api/*` | 変更なし |
| migration / DB schema | 変更なし |
