"""OANDA CFD instrument 疎通試験 (T005).

7 件の CFD 系 instrument に candles エンドポイントを試行し、
verdict (OK / FORBIDDEN / NOT_FOUND / OTHER) を判定する。
DB 書き込みは行わない。結果は JSON と Markdown レポートに出力。

仕様:
    | HTTP status | verdict | スクリプト挙動 |
    |---|---|---|
    | 200 | OK | 結果記録、続行 |
    | 401 | (fatal) | 即 abort, exit 1, JSON/MD は書かない |
    | 403 | FORBIDDEN | 結果記録、続行 |
    | 404 | NOT_FOUND | 結果記録、続行 |
    | 5xx (retry 失敗後) / 429 / TransportError / その他 | OTHER | 結果記録、続行 |

詳細設計: devnotes/20260422-1149-oanda-cfd-probe/detailed-design.md
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


@dataclass
class ProbeResult:
    """単一 instrument に対する probe 結果（JSON serialize されるため str/int/None のみ）。"""

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
    def from_results(cls, results: list[ProbeResult]) -> ProbeSummary:
        return cls(
            total=len(results),
            ok=sum(1 for r in results if r.verdict == "OK"),
            forbidden=sum(1 for r in results if r.verdict == "FORBIDDEN"),
            not_found=sum(1 for r in results if r.verdict == "NOT_FOUND"),
            other=sum(1 for r in results if r.verdict == "OTHER"),
        )


def probe_one(client: OandaClient, instrument: str) -> ProbeResult:
    """単一 instrument を probe する。401 は fatal（caller へ raise）。"""
    try:
        resp = client.get_candles(instrument, granularity="M1", price="BA", count=10)
    except OandaAuthError:
        # 既存 client が 401 を OandaAuthError に変換する経路 → そのまま caller へ
        raise
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 401:
            # 万一 client 実装が将来変わって 401 が HTTPStatusError として降ってきても
            # 必ず fatal 扱いにする二重防御。
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
    except Exception as exc:
        # 5xx retry 失敗 / TransportError / その他
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
    # 部分指定時のみ Settings を遅延 instantiate
    from src.config import Settings

    s = Settings()
    return (
        base_url or s.oanda_base_url,
        account_id or s.oanda_account_id,
        token or s.oanda_api_token,
    )


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
    """JSON 出力。datetime は明示的に isoformat 文字列に正規化。"""
    payload = {
        "probed_at": probed_at.isoformat(),
        "base_url": base_url,
        "results": [asdict(r) for r in results],
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
    lines.append("- granularity: M1, price: BA, count: 10")
    lines.append("")
    lines.append("## 結果サマリー")
    lines.append("")
    lines.append("| Instrument | verdict | status | candle_count | first_candle_time | error |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        err = (r.error_message or "")[:60]
        lines.append(
            f"| {r.instrument} | {r.verdict} | "
            f"{r.status_code if r.status_code is not None else '—'} | "
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
        lines.append(
            "- 全 instrument が OK。OANDA CFD ingest pipeline 拡張 TODO を別途起票し、"
            "FX と同じ M1 取得経路で取り込み実装へ進む。"
        )
    elif summary.ok == 0:
        lines.append(
            "- いずれの CFD instrument も取得不可。FRED + 自前計算 (realized_vol / "
            "usd_strength_synthetic) 強化で primitive を代替。"
        )
    else:
        lines.append(
            "- 部分的に取得可。OK 分は OANDA ingest TODO、不可分は FRED 代替 / "
            "FX データ完結 (realized_vol 等) primitive TODO の 2 本立てで進む。"
        )
    lines.append("")
    lines.append("## 観測 vs 解釈の分離（注記）")
    lines.append(
        "- verdict は観測事実のみを記録。FORBIDDEN / NOT_FOUND は **現 live/account/"
        "environment で当該 instrument の candles を取得できなかった** という事実に過ぎず、"
        "「永久に使えない」「OANDA に存在しない」と解釈してはならない。"
    )
    lines.append(
        "- account 区分・契約状態・地域規制等によって挙動が変わる可能性がある。"
        "代替経路を検討する際の入力情報として扱うこと。"
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe OANDA CFD instruments via candles endpoint")
    parser.add_argument("--instruments", nargs="+", default=list(DEFAULT_INSTRUMENTS))
    parser.add_argument(
        "--output-json", type=Path, default=DEFAULT_OUTPUT_DIR / "probe-result.json"
    )
    parser.add_argument(
        "--output-md", type=Path, default=DEFAULT_OUTPUT_DIR / "probe-report.md"
    )
    parser.add_argument("--base-url", default=None, help="Override OANDA base_url (e.g. for testing)")
    parser.add_argument("--account-id", default=None, help="Override OANDA account id")
    parser.add_argument(
        "--token", default=None, help="Override OANDA API token (avoid CLI; prefer .env)"
    )
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
