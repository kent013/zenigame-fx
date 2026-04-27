# 詳細設計: Stage A→B Pipeline Health Fix

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run 名・日付禁止）
- **uv 必須**: `uv run pytest tests/alpha_factory/`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`

## 概念設計リファレンス

[devnotes/20260427-1856-stage-pipeline-health-fix/conceptual-design.md](./conceptual-design.md)（Round 2 APPROVED）

主要決定事項:
- 主目的は **Stage B evaluability の回復**（速度改善は副次）
- 施策 0（投資調査）→ 施策 B（fold 修正）→ 施策 A（threshold 伝搬修正）→ A+B end-to-end の 4 段切り分け
- V2 で pass-rate 近似判定はしない、V4 で archive Parquet stage_*_pass を比較対象にしない
- cross-run contamination 防止: **base_config_hash**（適用判定用）/ **full_config_hash**（監査用）/ dataset_span / instrument / stage_gate_version / applied_from_run_id を必須メタデータ化
- decision filter 必須: `tighten/loosen` のみ適用、`in_band/skip_sample_size` 除外

---

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 0a | 純調査（コード変更なし、archive と log の読み取り） | `devnotes/{dir}/investigation.md`（新規） | High（Blocking） |
| 0b | 計測パッチ（fold reason 内訳保存、診断 log 追加） | `src/alpha_factory/stage_gate.py` / `src/alpha_factory/archive.py` / `scripts/alpha_factory/run_ga.py` / `tests/alpha_factory/` | High（B の前提） |
| B | Stage B all_folds_unavailable 修正 | 施策 0 結果次第（候補: `src/alpha_factory/stage_gate.py` / `src/backtest/walk_forward.py` / `config/alpha_factory/default.yaml`） | High |
| A | Stage A calibrate_gate 伝搬経路修正 | 施策 0 結果次第（候補: `scripts/alpha_factory/run_ga.py` / `scripts/alpha_factory/calibrate_gate.py` / 新規 state file 読込 module） | High |

---

## 施策 0: Investigation（A/B 共通 deliverable、2 段階）

### 目的
施策 A/B の実装方針は施策 0 結果に依存する。実装着手前の必須 deliverable。

**Round 1 [Warning] 4 反映: 0a / 0b に分割**:
- **0a**: 純調査（現行 archive と log の読み取りのみ、コード変更なし）
- **0b**: 計測パッチ（fold unavailable reason の内訳保存、診断ログ追加など。**別 commit / 別 PR**）

### 0a 変更箇所（成果物のみ、コード変更なし）
- `devnotes/20260427-1856-stage-pipeline-health-fix/investigation.md`（新規）

### 0b 変更箇所（計測パッチ、コード変更あり、別 commit）
- `src/alpha_factory/stage_gate.py`: fold unavailable reason の内訳カウント追加
- `src/alpha_factory/archive.py`: schema に `stage_b_unavailable_reason_counts` フィールド追加（既存 stage_b_reason_codes は維持、追加のみ）
- `scripts/alpha_factory/run_ga.py`: startup 時 `stage_gate.effective_threshold` イベント log 追加（source は `"config" | "history" | "cli"` の **単一値で必ず確定**、Round 2 [Warning] 反映）
- `tests/alpha_factory/`: 計測コード自体のテスト + reason 集計の不変条件テスト

**Round 2 [Warning] 反映: unavailable reason の排他的 enum 化**

```python
class FoldUnavailableReason(str, Enum):
    FOLD_EXCEPTION = "fold_exception"           # backtest 中の例外
    NO_TRADES = "no_trades"                     # trades 空
    TRADE_COUNT_BELOW_MIN = "trade_count_below_min"  # trade_count < trade_count_min_for_sharpe
    ZERO_VARIANCE = "zero_variance"             # trade returns の分散ゼロ
    OTHER = "other"                             # 上記以外（要 follow-up）
```

優先順位（最初にマッチした reason を採用、排他的）:
1. `FOLD_EXCEPTION`（例外発生は他の判定より優先）
2. `NO_TRADES`
3. `ZERO_VARIANCE`（trades あって 0 分散）
4. `TRADE_COUNT_BELOW_MIN`
5. `OTHER`

**不変条件テスト**: `sum(reason_counts.values()) == n_fold_unavailable`（必ず Pass）

- **Round 1 [Critical] 1 反映**: archive に reason 別カウントを保存しないと、施策 0a だけでは `invalid_fold_count_by_reason` を再構成できない
- **施策 0b は施策 B の前提**（0b で得たデータで仮説 B-X を検証）

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし

### 調査項目と必須出力

#### 0.1 Stage A threshold source-of-truth 図 (V0-A)

調査対象:
- `scripts/alpha_factory/run_ga.py`（startup での config 読み込み経路）
- `src/alpha_factory/config.py:375` (`stage_a_threshold = float(a_raw.get("threshold", 0.0))`)
- `scripts/alpha_factory/calibrate_gate.py`（出力先・適用先）

成果物:
- `[config.yaml] → [GaConfig] → [stage_gate evaluator]` の経路図（mermaid または箇条書き）
- `[history.jsonl] → ?` の経路図（経路があるか、なければ「なし」と明記）
- effective threshold の最終決定箇所と、summary.json への出力箇所

#### 0.2 run_ga effective threshold 実測ログ (V0-B)

run_ga.py に診断用 log 追加:
```python
logger.info(
    "stage_gate.effective_threshold",
    stage_a_threshold=cfg.stage_gate.stage_a_threshold,
    source="config|history|cli",  # source 識別
)
```

profile RUN（小規模）で実 log 出力を確認、investigation.md に貼る。

#### 0.3 summary.json field 意味確認 (V0-C)

source: `scripts/alpha_factory/run_ga.py` line 876 周辺の `"stage_a_threshold": cfg.stage_gate.stage_a_threshold,`

→ summary は `cfg.stage_gate.stage_a_threshold`（config 値）をそのまま出している。effective threshold = config 値ということが確認できれば「summary 表示ずれ」は除外できる。逆に runtime で override されている経路があれば不一致が出る。

#### 0.4 Stage B 実 bar 期間と fold 構築数の実測

調査対象 RUN:
- run_20260426_145502（Stage B pass=834 動作）
- run_20260426_183119（Stage B pass=0 停止）

集計項目（archive Parquet と関連 cache から抽出）:

| 項目 | run_20260426_145502 | run_20260426_183119 | 期待 |
|---|---|---|---|
| `bars_stage_b[0].time` | TBD | TBD | 18ヶ月前 |
| `bars_stage_b[-1].time` | TBD | TBD | dataset.end |
| `len(bars_stage_b)` | TBD | TBD | ~262080 |
| `n_fold` (constructed) | TBD | TBD | ~47 |
| `n_fold_unavailable` 平均 | TBD | TBD | <n_fold |
| `n_fold_effective` 平均 | TBD | 0 (verified) | >0 |
| `trade_count` per fold (median) | TBD | TBD | >=30 (= trade_count_min_for_sharpe) |

#### 0.5 前後 6 RUN の現象差分（C7 反映、n>=5 確保）

run-19 〜 run-24 の 6 RUN で:

| RUN | A pass rate | B pass count | reason top-3 | bars_stage_b len |
|---|---|---|---|---|
| run-19 | TBD | TBD | TBD | TBD |
| run-20 | 47.0% | TBD | TBD | TBD |
| run-21 | 40.9% | TBD | TBD | TBD |
| run-22 | 30.0% | TBD | TBD | TBD |
| run-23 | 38.2% | TBD | TBD | TBD |
| run-24 | 64.0% | 0 | all_folds_unavailable | TBD |

→ 「徐々に劣化」or 「単一切替点」を確定。

#### 0.6 git diff 候補 commit 一覧

施策 0.5 で切替点を確定後:
```bash
git log --all -S "all_folds_unavailable" --since="<切替前 RUN 日時>" --until="<切替後 RUN 日時>"
git log --all -S "n_fold_effective" --since=... --until=...
git log --all -S "trade_count_min_for_sharpe" --since=... --until=...
git log --all -- src/alpha_factory/stage_gate.py src/backtest/walk_forward.py scripts/alpha_factory/run_ga.py --since=... --until=...
```

成果物: 候補 commit 一覧 + 各 commit の影響範囲メモ。

#### 0.7 commit hash 記録（Round 2 [Suggestion] 反映）

施策 0 成果物の各実測項目に「実行時 commit hash」(`git rev-parse HEAD` 相当) を必須列として添える。仕様変更起因 vs データ regime 起因の切り分け強化。

### 仮説優先度（事前情報からの強度順、施策 0 で verify/refute）

1. **仮説 B-X（強）**: `trade_count_min_for_sharpe = 30` (src/alpha_factory/stage_gate.py:137) と Stage B の `wf_test_days = 10` (config) の組み合わせで、10 日の OOS 区間に 30 trade を要求 → ほぼ全個体で trade 不足 → 各 fold の `trade_sharpe_raw = None` → `n_fold_unavailable = n_fold` で all_folds_unavailable
   - 検証: 施策 0.4 で `trade_count` per fold の median を実測。30 未満なら仮説確認
   - 修正方向: 値の調整は禁止事項 4 (live_criteria 緩和) 違反になるか要 review。閾値の根拠と設計意図を再確認

2. **仮説 B-1**: bars_stage_b slicing バグ
3. **仮説 B-2**: fold validation の他条件が厳しくなった
4. **仮説 B-3**: fold time index 計算のバグ

### テスト計画（施策 0）
- なし（成果物は調査ドキュメントのみ）

### リスク
- 施策 0 の調査だけで原因が判明しなければ施策 A/B の修正方針が立たず本 TODO が長期化
- 軽減策: 施策 0 を 1-2 日で区切って一旦本 TODO を一時 close、結果次第で別 TODO 化（concept §7 INCONCLUSIVE 扱い）

---

## 施策 B: Stage B all_folds_unavailable 修正（施策 0 後）

### 変更箇所（施策 0 結果次第。仮説 B-X を採る場合の例）
- `src/alpha_factory/stage_gate.py:137` 周辺（`trade_count_min_for_sharpe` の値）
- `config/alpha_factory/default.yaml`（stage_b 関連 trade_count_min の追加 field）
- `tests/alpha_factory/test_stage_gate.py` または同等のテストファイル

### 波及変更
- `AGENTS.md`: 施策 0 結果次第。閾値の意味が変わる場合は運用ドキュメント更新
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし（コア skill は閾値直接参照しない）
- `config/alpha_factory/default.yaml`: 施策 0 結果次第（threshold が config 化される場合）
- `docs/alpha_factory/stage-gates.md`: 施策 0 結果に応じて Stage B fold validation 仕様を反映

### 修正方針（施策 0 結果に応じて分岐）

#### 仮説 B-X（trade_count_min_for_sharpe + wf_test_days 不整合）が verified の場合

**Round 1 [Critical] 3 反映: 統計要件の固定が先、経験式での緩和は禁止**

- 先に統計要件を固定する（修正前 deliverable）:
  - Sharpe 推定の最小サンプル数の根拠（学術引用 or 内部既往設計）
  - 例: Lo (2002) "The Statistics of Sharpe Ratios" による Sharpe の標準誤差は trade 数に依存。trade 数 N の Sharpe SE ≈ √((1+0.5×SR²)/N) → 一定の SE 上限を満たす N を逆算
- その統計要件を満たすために以下のどれを変えるかを **設計判断として記述**:
  - 案 1: `wf_test_days` を伸ばす（fold 期間延長は禁止事項 1 抵触の可能性。Stage B window_months=18 の中で fold 数が減る trade-off を明記してから判断）
  - 案 2: 利用指標を変える（trade-level Sharpe → 他の robust 指標、例えば bootstrap CI ベース判定）
  - 案 3: `trade_count_min_for_sharpe` を Stage B fold 専用閾値として独立化、統計要件から逆算した値に固定
- **経験式（例: `max(5, int(0.5 * wf_test_days))`）は禁止**（Round 1 [Critical] 3 反映、禁止事項 4 抵触）
- どの修正案でも **「機能していた当時の挙動を意図的に再現」**するもので、**緩めて pass を増やす hack ではない**ことを明示

#### 仮説 B-1〜B-3 が verified の場合
- B-1: slicing 修正、bar 数 invariant test 追加
- B-2: validation 条件の意図確認、当時の設計に戻す or 設計再定義
- B-3: time index 計算修正、time-axis 不変条件 test 追加

### テスト計画（共通）
- [x] 再現最小テスト（テストファースト）: 修正前は all_folds_unavailable、修正後は `n_fold_effective > 0`
- [x] 既存テスト維持: `tests/alpha_factory/test_stage_gate.py` 全パス
- [x] 新規テスト: fold validation 不変条件（trade_count_min と test_days の整合性、bar 数不変条件、time-axis 不変条件）

### リスク
- 修正により Stage B 通過率が大幅に変わる → 後続 Stage C 評価コストが増える可能性
- 緩和策: 修正後に小規模 RUN で reason code 分布を確認し、想定外の通過急増がないか check

---

## 施策 A: Stage A calibrate_gate 伝搬経路修正（施策 0 後、B 修正後）

### 変更箇所（施策 0 結果次第）
- `scripts/alpha_factory/run_ga.py`（startup hook 追加、約 30-50 行）
- `scripts/alpha_factory/calibrate_gate.py`（record メタデータ拡張）
- 新規モジュール `src/alpha_factory/calibrate_state.py`（state file read/validate ロジック、約 100 行想定）

### 波及変更
- `AGENTS.md`: 「calibrate-gate 結果が次 RUN に自動適用されるようになった」運用変更を反映
- `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md`: 適用フローの更新
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/runbook.md` / `docs/alpha_factory/stage-gates.md`: 適用経路を反映

### 修正方針（施策 0 §0.1 結果に応じて分岐）

#### 経路あり / 条件未充足の場合
- 条件を満たすように config 修正、または運用テンプレート（T051）の手順修正

#### 経路あり / 別 source of truth が優先の場合
- source of truth の整理（重複管理を解消）

#### 経路なし → state file 型を新規導入

新規モジュール `src/alpha_factory/calibrate_state.py`:

**Round 1 [Critical] 2 反映: hash の二系統化（自己矛盾防止）**
- `base_config_hash`: 適応値（stage_a_threshold 等の calibrate-gate が変更する field）を **除外** した config の hash → 適用判定に使う
- `full_config_hash`: 完全な config 全 field の hash → 監査用（不一致時は warn だが適用は継続可）

**Round 1 [Warning] 5 反映: schema_version + 値検証の追加**

```python
SCHEMA_VERSION = 1  # state file format version

def load_calibrated_threshold(
    history_path: Path,
    base_config_hash: str,         # 適応値 (stage_a_threshold) を除外した config hash
    dataset_span: tuple[datetime, datetime],
    instrument: str,
    stage_gate_version: str,
    *,
    threshold_floor: float = -100.0,
    threshold_ceiling: float = 100.0,
) -> float | None:
    """history.jsonl の最新 record から effective threshold を読み出す。

    cross-run contamination 防止のため、以下を全て verify (fail-closed):
    - record.schema_version == SCHEMA_VERSION
    - record.base_config_hash == 引数 base_config_hash（適応値除外の hash 比較）
    - record.dataset_span == 引数 dataset_span
    - record.instrument == 引数 instrument
    - record.stage_gate_version == 引数 stage_gate_version
    - record.decision in ("tighten", "loosen")  # in_band / skip_sample_size 除外
    - record.applied_at が ISO 8601 形式
    - record.new_threshold が isfinite かつ [threshold_floor, threshold_ceiling] 内

    一致しない record があれば skip。最新 record が verify できない場合は None
    （= config 値を使用）。fail-closed のため、不正値があれば WARN log + None を返す。
    """
```

補助関数（`src/alpha_factory/calibrate_state.py` 内に併設）:
```python
def compute_base_config_hash(cfg: GaConfig) -> str:
    """適応値 (stage_a_threshold 等の calibrate-gate 変更対象) を除外した
    config hash を計算する。Round 1 [Critical] 2 自己矛盾防止のための専用関数。

    除外対象 fields (calibrate-gate が変更しうる適応値):
    - cfg.stage_gate.stage_a_threshold
    （以降、calibrate 対象が増えるたびに本関数の除外リストに追加）

    返り値: hex digest (sha256 or blake2b)
    """

def compute_full_config_hash(cfg: GaConfig) -> str:
    """完全 config hash（監査記録専用、適用判定には使わない）。"""
```

`run_ga.py` startup での適用（**Round 2 [Critical] 反映: `base_config_hash` 引数で統一**）:
```python
# config 読み込み後、stage_gate evaluator 構築前
calibrated = load_calibrated_threshold(
    history_path=Path("reports/calibrate-gate/history.jsonl"),
    base_config_hash=compute_base_config_hash(cfg),  # ← 適応値除外の hash
    dataset_span=(cfg.dataset.start, cfg.dataset.end),
    instrument=cfg.dataset.instrument,
    stage_gate_version=STAGE_GATE_VERSION,
)
threshold_source: Literal["config", "history", "cli"] = "config"  # default
if calibrated is not None:
    logger.info(
        "stage_gate.threshold_override",
        old=cfg.stage_gate.stage_a_threshold,
        new=calibrated,
        source="history",
    )
    cfg.stage_gate.stage_a_threshold = calibrated
    threshold_source = "history"
# CLI override がある場合は --max-workers と同様の経路で source="cli" に
logger.info(
    "stage_gate.effective_threshold",
    stage_a_threshold=cfg.stage_gate.stage_a_threshold,
    source=threshold_source,  # "config" | "history" | "cli" の単一値（必ず確定）
)
```

calibrate_gate.py の record 出力時:
```python
record = {
    ...,
    "schema_version": SCHEMA_VERSION,             # 1
    "base_config_hash": compute_base_config_hash(cfg),  # 適用判定用
    "full_config_hash": compute_full_config_hash(cfg),  # 監査専用
    "dataset_span": [str(start), str(end)],
    "instrument": instrument,
    "stage_gate_version": STAGE_GATE_VERSION,
    "applied_from_run_id": run_id,
}
```

`scripts/alpha_factory/calibrate_gate.py` の record 出力に以下メタデータを必須追加:
- `base_config_hash`: 適応値除外、適用判定用（必須）
- `full_config_hash`: 完全 config、監査用（必須）
- 旧 `config_hash` field は **互換読み取り専用**（新規書込みでは出力しない、既存 record に残っていても適用判定では使わない）
- `dataset_span`: `(start, end)` の tuple
- `instrument`: 通貨ペア
- `stage_gate_version`: 定数（バージョン管理は別 TODO）
- `applied_from_run_id`: 適用元 RUN

### テスト計画
- [x] 再現最小テスト: history.jsonl が空 → None、record あり / メタデータ一致 → threshold 適用
- [x] cross-run contamination 防止: base_config_hash mismatch / dataset_span mismatch / instrument mismatch / decision="in_band" 等で None
- [x] decision フィルタ: tighten/loosen のみ適用、in_band/skip_sample_size は除外
- [x] 適用順序: 複数 record があれば最新の適用可能 record を採用
- [x] log 出力: threshold_override イベントが effective threshold で出る
- [x] **CLI override 優先順位**（Round 3 [Suggestion] 反映）: history 適用あり + CLI 指定あり の場合、最終 source は `cli`（CLI が history より優先）。テスト名 `test_threshold_source_cli_overrides_history`

### リスク
- state file 形式の変更で過去の history.jsonl record が読めなくなる
- 緩和策: 後方互換 (`record.get("base_config_hash", None)` → None なら適用しない fail-closed。旧 `config_hash` only の record は新規書込みでは作らないため自然に置換される)
- worker 並列 RUN で history.jsonl への同時書込競合 → 緩和策: 既存 calibrate_gate.py の書込み挙動を継承（書込みは run 完了後 1 回のみのため衝突はない）

---

## ルックアヘッドバイアスチェック
primitive 変更なし、該当なし（Round 2 [Warning] 反映で明示）。

## パフォーマンスチェック
本 TODO の主目的は機能修復であり、性能事前見積りなし（concept §3.2 反映）。実装後に stage-wise wall-clock を再計測。

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone**（concept §4.1 の 4 段切り分け運用が前提） |
| 判断根拠 | (1) 施策 0 の調査結果に依存して施策 A/B の方針が変わる、(2) 施策 B → A → A+B の段階評価が必要、(3) cross-run contamination 防止のためメタデータ拡張が伴う |
| 競合リスク | T053（composite Numba）と independent。calibrate-gate-drift（T051）の運用テンプレートと競合の可能性あり、施策 A 実装時に再確認 |
| 想定実装時間 | 中-長（施策 0 で 1-2 日、施策 B で 1 日、施策 A で 1-2 日。合計 1 週間想定） |

---

## 検証要件まとめ

| # | 項目 | 合格基準 |
|---|---|---|
| V0-A | source-of-truth 図 | 1 枚の経路図が存在し source of truth が 1 つ |
| V0-B | effective threshold log | startup で「使われた effective threshold」が log 出力 |
| V0-C | summary field 意味確認 | summary.json `stage_a_threshold` field が effective threshold を表すか確認 |
| V1 | 原因 commit / 仕様変更の特定 | 施策 0 §0.6 で commit 候補一覧、または「commit ではなく仕様/データ regime 変更」と結論 |
| V2 | 小規模 RUN 機能確認（pop=8, gen=2） | (a) override が読まれた、(b) effective threshold が期待値、(c) reason code が単色でない、(d) `n_fold_effective > 0` の個体が少なくとも 1 出る。**pass-rate 近似判定はしない** |
| V3 | 本番 RUN 機能確認（pop=96, gen=60） | **必須**: (a) `n_fold_effective > 0` の個体出現、(b) reason code 単色解消、(c) stage_a_pass_rate ≈ target ± tolerance。**参考 KPI**: stage_b_pass_count >= 1。**統計仕様の事前固定**（Round 1 [Suggestion] 反映）: seed 数 = 3、target tolerance = ±0.07、判定ロジック = 3 seed 中 2 seed 以上で必須 (a)(b)(c) を満たす |
| V4 | 数値同値性（適用範囲限定） | T053 の composite/backtest 数値契約は **不変**（同一 genome × 同一 bars に対する `compute_composite` 結果が allclose）。Stage A/B/C 判定値・stage_*_pass フィールドは **比較対象外** |
| V5 | 既存テスト | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x` 全パス |
| V6 | 新規テスト | 施策 A: state file load + cross-run contamination ガード + decision filter。施策 B: fold validation 不変条件、time-axis 不変条件、bar 数 invariant |
| V7 | ruff / mypy | `uv run ruff check src/ tests/` PASS, `uv run mypy src/` PASS |

INCONCLUSIVE 扱い:
- 施策 0 で「単一 commit ではなくデータ regime / 仕様変更」と判明 → 施策 B の方針を「動いていた当時の挙動を再現する仕様の再 design」に切り替え。Round 増しが必要なら本 TODO を一旦 close、別 TODO 化
