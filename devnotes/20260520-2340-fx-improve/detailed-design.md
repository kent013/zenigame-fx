# 詳細設計: Run 83 施策

## 使命・制約（絶対遵守）
- 使命: live_criteria 全達成個体を 1 つ見つける。Stage C 通過は最低条件。
- FX 固有制約: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッド控除後純利益で評価。
- 本施策は **観測機構の純追加**。GA hot path の挙動・gate 閾値・fitness・探索空間を一切変更しない（行動変更なし）。

## 施策一覧
| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | Stage B→C gap diagnostic v1 | `src/alpha_factory/diagnostics_collector.py`, `src/alpha_factory/diagnostics_sidecar.py`, `src/alpha_factory/swim_lane.py` | Total PnL / Trade Count（C 全滅の主因分解 → 次サイクルの構造施策選択） |

---

## C1: Stage B→C gap diagnostic v1

### target_metric / failure_mode / causal_path / falsification / success_criterion
- target_metric: Stage C 通過個体の出現（C>0）に向けた、C 全滅の主因（count 不足 / pnl 不足 / cost stress）の分解。
- failure_mode: Run82 で B=941 全件が Stage C で全滅。holdout 短窓 + stress 下で trade_count が崩れる頻度不足が疑われるが因果未分解。
- causal_path: Stage C 評価時に既に計算済みの `live_criteria_pass`・`stress.pnl_degradation`・base/stress `trade_count` を per-individual sidecar に永続化 → 次サイクルで主因比率を機械集計 → 因果に基づき次の構造施策（① cost stress 前倒し or ② 直近整合 selection）を選択。
- falsification: sidecar に gap_class 列が出ない / 全件 null で主因分離不能。
- success_criterion: R83 sidecar に全 Stage-C 評価個体ぶんの gap_class が出力され、`count_only`/`pnl_only`/`both_pnl_count` 比率が集計可能。

### 設計方針
Stage C の `StageResult.metrics["payload"]` には既に分類に必要な全データが存在する（stage_gate.py:2229-2260）:
- `payload["live_criteria_pass"]`: `{sharpe, total_pnl, max_drawdown, trade_count_min, trade_count_max}` の bool dict
- `payload["total_pnl"]`, `payload["trade_count"]`: base（unstressed）holdout 値
- `payload["stress"]`: `{pnl_degradation (=base-stress), trade_count, total_pnl, sharpe_degradation, skipped}`
- `result.reason_codes`: 失敗理由 tuple（`system_failure` 含む）

→ 新規 backtest 実行は不要。既存 payload を読んで分類・記録するだけ。

### 変更箇所

#### (1) `diagnostics_collector.py` — 分類関数 + record_stage_c 拡張

**現行コード（record_stage_c, 138-151 行）**:
```python
    def record_stage_c(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        passed: bool,
    ) -> None:
        """Stage C pass/fail を記録。Stage A 未記録なら no-op (defensive)."""
        rec = self._records.get(
            self._key(lane_id, generation, individual_name)
        )
        if rec is None:
            return
        rec.stage_c_pass = bool(passed)
```

**変更後**: `passed: bool` → `result: StageResult`（record_stage_a と同型）に変更し、payload から gap 診断を抽出。

```python
    def record_stage_c(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        result: StageResult,
    ) -> None:
        """Stage C 結果を記録。Stage A 未記録なら no-op (defensive).

        T<id>: B→C gap diagnostic v1。base live_criteria 失敗の組合せを
        固定コードで分類し、stress PnL 劣化量と base/stress trade_count を
        記録する（観測のみ、passed 判定には一切影響しない）。
        """
        rec = self._records.get(
            self._key(lane_id, generation, individual_name)
        )
        if rec is None:
            return
        rec.stage_c_pass = bool(result.passed)
        diag = _derive_stage_c_gap(result)
        rec.stage_c_gap_class = diag["gap_class"]
        rec.stage_c_base_total_pnl = diag["base_total_pnl"]
        rec.stage_c_base_trade_count = diag["base_trade_count"]
        rec.stage_c_stress_pnl_degradation = diag["stress_pnl_degradation"]
        rec.stage_c_stress_trade_count = diag["stress_trade_count"]
```

**新規モジュール関数 `_derive_stage_c_gap`**（payload を defensive read、例外時は安全な null/`unknown`）:
```python
# gap_class enum（CI invariant 用に固定集合）
VALID_STAGE_C_GAP_CLASSES: Final[frozenset[str]] = frozenset({
    "pass", "pnl_only", "count_only", "both_pnl_count",
    "sharpe_involved", "mixed", "stress_or_other", "system_fail", "unknown",
})

def _derive_stage_c_gap(result: StageResult) -> dict[str, Any]:
    """Stage C StageResult から gap 診断を抽出（新規 backtest なし、純 read）。

    分類優先順位（排他）:
      1. system_fail        : reason に system_failure OR worker_error
                              （並列パスの worker_error StageResult は
                               live_criteria_pass を持たない実行時障害 →
                               実行失敗として system_fail に集約。Codex
                               design-review Round 1 [Critical] 反映）
      2. pass               : result.passed
      3. base live_criteria 失敗の組合せ:
           both_pnl_count   : total_pnl ∧ trade_count 両方 fail
           pnl_only         : total_pnl のみ fail（count ok）
           count_only       : trade_count のみ fail（pnl ok）
           sharpe_involved  : sharpe が fail に含まれる（上記以外）
           mixed            : 上記以外の base lc 失敗組合せ
      4. stress_or_other    : base lc 全通過だが stress / intraday 等で fail
      5. unknown            : payload 不整合（defensive）
    """
    out: dict[str, Any] = {
        "gap_class": "unknown",
        "base_total_pnl": None, "base_trade_count": None,
        "stress_pnl_degradation": None, "stress_trade_count": None,
    }
    try:
        # Codex design-review Round 2 [Suggestion]: reason_codes を payload 型
        # チェックより前に抽出。payload 自体が壊れた system_failure/worker_error
        # も確実に system_fail へ寄せる。
        reasons = tuple(getattr(result, "reason_codes", ()) or ())
        if ("system_failure" in reasons) or ("worker_error" in reasons):
            out["gap_class"] = "system_fail"; return out
        payload = result.metrics.get("payload", {}) if hasattr(result, "metrics") else {}
        if not isinstance(payload, dict):
            return out
        # raw 値（finite 化）
        out["base_total_pnl"] = _safe_float(payload.get("total_pnl"))
        out["base_trade_count"] = _safe_int(payload.get("trade_count"))
        stress = payload.get("stress")
        if isinstance(stress, dict) and not stress.get("skipped", False):
            out["stress_pnl_degradation"] = _safe_float(stress.get("pnl_degradation"))
            out["stress_trade_count"] = _safe_int(stress.get("trade_count"))
        # （system_fail 判定は上で reason_codes 抽出直後に実施済み）
        if bool(result.passed):
            out["gap_class"] = "pass"; return out
        lcp = payload.get("live_criteria_pass", {})
        if not isinstance(lcp, dict):
            out["gap_class"] = "unknown"; return out
        pnl_fail = lcp.get("total_pnl") is False
        count_fail = (lcp.get("trade_count_min") is False) or (lcp.get("trade_count_max") is False)
        sharpe_fail = lcp.get("sharpe") is False
        dd_fail = lcp.get("max_drawdown") is False
        base_lc_fail = pnl_fail or count_fail or sharpe_fail or dd_fail
        if not base_lc_fail:
            out["gap_class"] = "stress_or_other"; return out
        if pnl_fail and count_fail:
            out["gap_class"] = "both_pnl_count"
        elif pnl_fail and not (count_fail or sharpe_fail or dd_fail):
            out["gap_class"] = "pnl_only"
        elif count_fail and not (pnl_fail or sharpe_fail or dd_fail):
            out["gap_class"] = "count_only"
        elif sharpe_fail:
            out["gap_class"] = "sharpe_involved"
        else:
            out["gap_class"] = "mixed"
        return out
    except Exception:
        return out  # fail-soft: 診断は観測専用、絶対に評価を壊さない
```
（`_safe_float` / `_safe_int`: None/NaN/Inf/型不正を None に潰す小ヘルパ。既存 record_stage_a の finite ガードと同型）

**`IndividualDiagnostics` への field 追加（42-53 行）**:
```python
    stage_c_gap_class: str | None = None
    stage_c_base_total_pnl: float | None = None
    stage_c_base_trade_count: int | None = None
    stage_c_stress_pnl_degradation: float | None = None
    stage_c_stress_trade_count: int | None = None
```

**`to_rows` への追加（176-189 行の dict に append）**:
```python
                    "stage_c_gap_class": rec.stage_c_gap_class,
                    "stage_c_base_total_pnl": rec.stage_c_base_total_pnl,
                    "stage_c_base_trade_count": rec.stage_c_base_trade_count,
                    "stage_c_stress_pnl_degradation": rec.stage_c_stress_pnl_degradation,
                    "stage_c_stress_trade_count": rec.stage_c_stress_trade_count,
```
`to_rows` の既存 assert（metric_stage enum）に加え、`assert rec.stage_c_gap_class is None or rec.stage_c_gap_class in VALID_STAGE_C_GAP_CLASSES` を追加（CI invariant）。

#### (2) `diagnostics_sidecar.py` — schema に nullable 5 列追加

**`STAGE_A_PROVENANCE_SCHEMA`（51-68 行）末尾に追加**:
```python
        # T<id>: Stage B→C gap diagnostic v1（全列 nullable, v2 互換の additive 拡張）
        pa.field("stage_c_gap_class", pa.string(), nullable=True),
        pa.field("stage_c_base_total_pnl", pa.float64(), nullable=True),
        pa.field("stage_c_base_trade_count", pa.int32(), nullable=True),
        pa.field("stage_c_stress_pnl_degradation", pa.float64(), nullable=True),
        pa.field("stage_c_stress_trade_count", pa.int32(), nullable=True),
```
- `DIAGNOSTICS_SCHEMA_VERSION` は **2 のまま据え置く**（追加は全 nullable、v2 contract の required field 集合は不変。`assert_diagnostics_v2` は required field のみ検証するため追加列は問題なし）。
- `build_sidecar_table` は `to_rows()` の dict をそのまま `from_pylist(schema=...)` するため、schema に列追加すれば自動で出力される。Stage A/B 止まりの個体は新列 null（nullable=True で整合）。

#### (3) `swim_lane.py` — record_stage_c 呼出 2 箇所

**逐次パス（688-693 行）**:
```python
                self._diagnostics.record_stage_c(
                    lane.lane_id,
                    lane.generation_count,
                    genome.name,
                    c_result,          # was: bool(c_result.passed)
                )
```
**並列パス（888-893 行）**: 同様に `bool(c_result.passed)` → `c_result`。
（両 call site とも有効な StageResult `c_result` を保持していることを確認済み: 逐次 670 行 / 並列 883 行で代入。）

### 波及変更（AGENTS.md / skill / config / docs）
- **config**: なし（新規 config 項目なし、行動変更なし）。
- **AGENTS.md**: GA 引数 / CLI / 公開 API 変更なし → 不要。
- **skill**: 公開インターフェース変更なし → 不要。
- **docs**: `docs/alpha_factory/` の sidecar スキーマ記述があれば新列 5 つを追記（存在確認のうえ実装フェーズで対応）。run-report skill が sidecar 列を固定参照していないか確認（追加列は無視されるため後方互換）。

### ルックアヘッドバイアスチェック（primitive 変更なし → N/A）
- primitive / backtest ロジックは一切変更しない。観測値の読取のみ。該当なし。

### パフォーマンスチェック
- 新規 backtest 実行なし。record_stage_c で payload dict を 1 回読むだけ（O(1)、per-individual）。GA wall-time への影響は無視可能。
- sidecar Parquet に 5 列 × 行数（≈ Stage A 評価個体数）追加 → ファイルサイズ微増のみ。

### テスト計画
- [ ] `_derive_stage_c_gap` の unit test: 各 gap_class（pass / pnl_only / count_only / both_pnl_count / sharpe_involved / mixed / stress_or_other / system_fail / unknown）を合成 StageResult で検証。
- [ ] stress skipped / payload 欠落 / reason_codes 空 の defensive ケースで例外を出さず安全 default を返すこと。
- [ ] **worker_error sentinel**（reason_codes=("worker_error",) かつ payload に live_criteria_pass なし）が `system_fail` に分類されること（Codex Round 1 [Critical] 対応）。
- [ ] `record_stage_c` シグネチャ変更に伴う既存テスト更新（`bool` → `StageResult` 渡し）。
- [ ] `to_rows` が新 5 列を含むこと + gap_class enum invariant assert。
- [ ] `build_sidecar_table` / `write_stage_a_provenance` の integration test: 新列が Parquet に出力され、Stage A 止まり個体は null、schema mismatch warning が出ないこと。
- [ ] 既存 sidecar regression: 既存列・行数・metric_stage enum が不変。

### リスク
- **低**。観測専用・fail-soft（`_derive_stage_c_gap` は全例外を握り潰し安全 default）。GA 評価結果・gate・fitness・sidecar の既存列に影響なし。
- 唯一の波及は `record_stage_c` のシグネチャ変更（2 call site + テスト）。両 call site とも有効な StageResult を保持しているため安全。
- schema version 据え置きの妥当性は Codex レビューで確認（追加列が全 nullable かつ required contract 不変なら v2 のままで可と判断）。

## Run 83 実行パラメータ
| パラメータ | 値 | R82 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 不変 |
| population-size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation-rate | 0.5 | 不変 |
| seed | 68 | 67 → 68（seed sweep 継続、行動変更なしのため diagnostic 検証用に通常進行） |
| max-workers | 2 | 不変 |
| stage-b-gate-kind | profit_safe_pfr | 不変 |

> 注: C1 は行動変更なしのため、R83 の GA dynamics は seed 差以外 R82 と同等の想定。diagnostic 列が全 Stage-C 評価個体ぶん出力されることが第一の成功条件。
