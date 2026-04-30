# 詳細設計: T074 — Graduation lane batch evaluator scaffold

**作成日時**: 2026-05-01 01:35 JST
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 3 APPROVED 済 (`conceptual-review-round-3.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 / §4 の擬似コードは概念設計 §4 / §5 / §6 と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `323055b` (T073 commit 後)

**改訂履歴 (Round 3 詳細レビュー反映、 2026-05-01 03:00 JST)**: 0 Critical + W1-W4 + S1-S4 を全反映:
- Round D3 [W1]: GraduationTriggerEvaluation に **cross-field invariant 追加**:
  - `len(set(recent_mission_pass_epoch_ids)) == len(recent_mission_pass_epoch_ids)` (= duplicate 禁止)
  - `n_distinct_epochs >= len(recent_mission_pass_epoch_ids)` (= mission pass epoch ⊆ distinct epoch)
- Round D3 [W2]: `tier1_event` のような identifier は **exact name (= "tier1") のみ reject、 substring "tier1_event" は許容** と仕様明記
- Round D3 [W3]: AST grep DoD test の ImportFrom check に **alias.name も対象追加** (= `from . import archive` の検出)
- Round D3 [W4]: forbidden_substrings の **case-sensitivity を明記** (= "DST" 大文字 substring は case-sensitive、 "dst_xxx" は検出しない方針)
- Round D3 [S1]: Phase 2 adapter contract 3 案の **推奨順を A > B > C** と明記、 C は production 推奨不可
- Round D3 [S2]: synthesis Round 22 改訂 PR で **`synthesis_schema_version: 22` を明示追加** と申し送り強化
- Round D3 [S3]: F22f / F22g に境界 case 追加 (= len=0 と len=required-1 / len=required と len>required)
- Round D3 [S4]: F22e parametrize は test 内 valid baseline fixture + override matrix で実装

**改訂履歴 (Round 2 詳細レビュー反映、 2026-05-01 02:30 JST)**: 0 Critical + W1-W4 + S1-S4 を全反映:
- Round D2 [W1]: `recent_mission_pass_epoch_ids` を **「実測 diagnostic field」** として SSOT 化。 status="ready" は完全一致、 status="no_recent_mission_pass" は **partial pass を許容** (= 0 <= len < recent_epochs_required)、 status=insufficient_* は size=0 (= 早期 return)
- Round D2 [W2]: AST grep DoD test に **`ast.Constant(str)` 検出を追加**、 ただし docstring (= ast.Module / FunctionDef / ClassDef の最初の statement) は除外
- Round D2 [W3]: forbidden_word_substrings 系を **identifier 完全一致 + 別途 substring** に分離 (= `Tier1Lane` exact / `tier1` も exact 名 / substring `holiday` 等は別 list)、 false positive 排除
- Round D2 [W4]: Phase 2 申し送りに「既存 archive.py に transaction/snapshot API が無ければ Phase 2 PR で snapshot DTO or transaction wrapper を追加実装」 を明記
- Round D2 [S1]: insufficient_epochs invariant `n_graduates >= 24` を維持 (= priority 正規化済 status invariant)
- Round D2 [S2]: robust 追加禁止規範を **`synthesis_schema_version >= 22`** (= synthesis のバージョン ID 基準) に変更、 commit hash 廃止
- Round D2 [S3]: F22e_status_invariant_complete を pytest **parametrize で実装**、 4 status × invariant matrix
- Round D2 [S4]: `src.alpha_factory.__init__.py` re-export 不要 (Phase 1)、 公開 API 段階で再判断

**改訂履歴 (Round 1 詳細レビュー反映、 2026-05-01 02:00 JST)**: C1 + W1-W8 + S1-S4 を全反映:
- Round D1 [C1]: `recent_epochs_required >= 1` invariant を **GraduationTriggerEvaluation.__post_init__ にも明示** (= evaluate_graduation_trigger 引数バリデーションのみだと dataclass 構築側で 0 が通る)
- Round D1 [W1]: SSOT 文言で `.issubset()` に統一 (= `<=` は併記しない、 真部分集合 `<` の誤読排除)
- Round D1 [W2]: GraduationArchiveSummary.__post_init__ の raise 順序 (I-1 → I-2 → I-3 → I-4) を **「仕様」 として固定**、 docstring 明記
- Round D1 [W3]: GraduationTriggerEvaluation の status 別 invariant を `recent_mission_pass_epoch_ids` の真偽式まで完全網羅
- Round D1 [W4]: F9-F14 に `n_graduates<0` / recent duplicate / recent not in distinct fail case を追加
- Round D1 [W5]: F22 系に `recent_epochs_required<=0` / dataclass 直接構築での違反 fail case 追加
- Round D1 [W6]: import パス `src.alpha_factory.graduation` で確定 (= 既存 tests/alpha_factory/test_*.py 慣行に整合、 grep 確認済)
- Round D1 [W7]: F27 grep DoD を **AST/tokenize ベース**に変更 (= docstring/comment 内 substring の false positive 排除)
- Round D1 [W8]: Phase 2 adapter contract に I/O 最小契約 (= 入力 snapshot 条件 / 出力 summary 一貫性 / 失敗時 raise 規約) を追記
- Round D1 [S1]: `_make_trigger` を keyword-only signature (`*` 区切り) で固定、 詳細擬似コード明示
- Round D1 [S2]: Round 3 [S4] robust 系追加禁止規範を「synthesis 改訂前」 = synthesis Round 22 改訂 commit 確定前 と日付/version 基準で固定
- Round D1 [S3]: C2 parallel-path grep 検索語に `seed_graduates`, `tier1`, `Tier1Lane` を追加 (= 13 検索語に拡張)
- Round D1 [S4]: 設計書内に `Fact / Interpretation` 小節 template を置くは概念設計時点で実施済 (= Round 1-3 各 review で本テンプレ採用済)、 詳細設計は変更不要

**改訂履歴 (旧)**: 概念設計 Round 1-3 で出た指摘は概念設計に全反映済。 概念 Round 3 で残った Warning (W1-W4) / Suggestion (S1-S4) を本詳細設計で反映:
- Round 3 [W1]: `mission_pass_run_ids <= observed_run_ids` (= `frozenset.issubset` SSOT、 inclusive)、 数学記号 `⊂` (= 真部分集合) と解釈しない (= 全 observed run が mission_pass の epoch を弾かない)
- Round 3 [W2]: `recent_epoch_summaries[1:]` の順序正当性は `__post_init__` のみでは検出不能、 Phase 2 adapter test の責務として明文化
- Round 3 [W3]: `has_recent_mission_pass` は「**trigger status 上の成立フラグ**」 (= status="ready" 時のみ True、 実データ独立評価ではない) を docstring 固定
- Round 3 [W4]: `archive_epoch_id_active=None` は empty archive 専用、 「active epoch あるが recent summary 未構築」 中間状態は別 TODO で contract 拡張
- Round 3 [S1]: `recent_epoch_summaries` を「新しい順、 [0] が active/current、 以降古い epoch」 と docstring 表現
- Round 3 [S2]: Phase 2 config キー仮名 `graduation.recent_epochs_with_mission_pass_required`、 missing は ValueError fail-closed
- Round 3 [S3]: grep DoD に `promote_graduates`, `mark_graduated`, `GraduationLane` 追加 (= 既存 swim_lane 非侵襲監査強化)
- Round 3 [S4]: robust 系 aggregation は Phase 4 で synthesis 改訂前に `Literal` 追加禁止 SSOT

## 0. 詳細設計の責務

概念設計で確定した SSOT (= 純ライブラリ / epoch 基準 / caller 引数 N / frozenset 6 pair / status field 方式 / scaffold T073 SSOT 継承 / collider bias Phase 2 申し送り) を **コード単位** に展開:
- 完全な擬似コード
- subset SSOT を `frozenset.issubset` で固定 (Round 3 [W1])
- recent order docstring 厳密化 + Phase 2 adapter test の責務 (Round 3 [W2] [S1])
- has_recent_mission_pass の status 従属性 docstring 固定 (Round 3 [W3])
- adapter contract Phase 2 申し送り強化 (Round 3 [W4] [S2])
- grep DoD 10 検索語 (Round 3 [S3])

## 1. ファイル / 関数 / クラス完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/alpha_factory/graduation.py` | `GraduationTriggerStatus`, `MultiPairAggregationKind`, `MultiPairAggregationStatus`, `GRADUATION_TRIGGER_MIN_GRADUATES`, `GRADUATION_TRIGGER_MIN_EPOCHS`, `GRADUATION_BATCH_PAIRS`, `LANE_PARALLELISM`, `GRADUATION_REPORT_SCHEMA_VERSION`, `GRADUATION_TRIGGER_CALC_VERSION`, `GRADUATION_AGGREGATION_CALC_VERSION`, `GraduationEpochSummary`, `GraduationArchiveSummary`, `GraduationTriggerEvaluation`, `MultiPairAggregationSketch`, `evaluate_graduation_trigger`, `compute_multi_pair_aggregation_sketch` | +200 |
| `tests/alpha_factory/test_graduation.py` | F1-F25 + happy path | +280 |

### 1.2 既存ファイル変更

| Path | 関数 / 行 | 変更内容 | LOC 増減 |
|---|---|---|---|
| (なし) | T074 PR は新規 module + 単体テストのみ | 既存ファイルへの影響なし | 0 |

### 1.3 Phase 2 申し送り (T074 PR では touch しない)

- T071 詳細設計改訂: `RunObservabilityReport.graduation_trigger: GraduationTriggerEvaluation` field 追加 (= status field 方式整合)
- run_ga.py 詳細設計改訂: 唯一の SSOT adapter として archive 集計 → GraduationArchiveSummary 構築 (Round 3 [W2] adapter test 含む)
- config 詳細設計改訂: `graduation.recent_epochs_with_mission_pass_required` キー追加、 missing は ValueError fail-closed (Round 3 [S2])
- T064 詳細設計改訂: STAGE_C_ANCHOR_PAIR / STAGE_C_SHADOW_PAIR_LIST と GRADUATION_BATCH_PAIRS の整合は T074 PR で test 側のみ確認 (= production module 不変、 概念 Round R2 [S4])

### 1.4 Phase 4 申し送り

- multi-pair 集約計算実装 (= worst_pair / mean)
- GraduationLane.run_generation の実装 (= NotImplementedError → 実装)
- GraduationBatchInput / GraduationBatchReport dataclass 導入 (Phase 1 では死蔵 risk 排除)
- robust 系 aggregation (= worst-case CVaR 等) は **synthesis 改訂前に MultiPairAggregationKind Literal に追加禁止** (Round 3 [S4])
- GRADUATION_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 (MINOR bump、 後方互換)

## 2. 既存 caller signature 完全展開

### 2.1 既存挙動への影響なし

T074 PR は新規 module 追加のみ。 既存 caller (= swim_lane.py / archive.py / cross_pair.py の caller) には影響しない。

### 2.2 grep DoD (Round 3 [S3] / Round D1 [S3] 13 検索語)

```bash
# T074 PR 実装時の確認

# 1. graduation.py を src/ から import する経路 0 件 (= tests のみ)
grep -rn "from src.alpha_factory.graduation import\|import src.alpha_factory.graduation" src/ --include="*.py"
# 期待: 0 件

grep -rn "from src.alpha_factory.graduation import\|import src.alpha_factory.graduation" tests/ --include="*.py"
# 期待: 1 件 (= tests/alpha_factory/test_graduation.py のみ)

# 2. 検索語 (Round R2 [S3] 7 語 + Round 3 [S3] 3 語追加 = 10 語):
grep -rn "\barchive\b" src/alpha_factory/graduation.py        # (1) archive 経路、 graduation.py 内 0 件
grep -rn "\bswim_lane\b" src/alpha_factory/graduation.py     # (2) swim_lane 経路、 0 件
grep -rn "\bcross_pair\b" src/alpha_factory/graduation.py    # (3) cross_pair 経路、 0 件
grep -rn "\bANCHOR_PAIRS\b" src/alpha_factory/graduation.py   # (4) cross_pair.ANCHOR_PAIRS 命名衝突、 0 件
grep -rn "\bholiday\b" src/alpha_factory/graduation.py       # (5) collider bias、 0 件
grep -rn "\bDST\b" src/alpha_factory/graduation.py           # (6) collider bias、 0 件
grep -rn "\bobservability_flags\b" src/alpha_factory/graduation.py   # (7) collider bias、 0 件
grep -rn "\bpromote_graduates\b" src/alpha_factory/graduation.py     # (8) Round 3 [S3]、 既存 swim_lane 非侵襲、 0 件
grep -rn "\bmark_graduated\b" src/alpha_factory/graduation.py        # (9) Round 3 [S3]、 既存 archive 非侵襲、 0 件
grep -rn "\bGraduationLane\b" src/alpha_factory/graduation.py        # (10) Round 3 [S3]、 既存 swim_lane.GraduationLane 非侵襲、 0 件
grep -rn "\bseed_graduates\b" src/alpha_factory/graduation.py        # (11) Round D1 [S3]、 既存 swim_lane.seed_graduates 非侵襲、 0 件
grep -rn "\btier1\b" src/alpha_factory/graduation.py                 # (12) Round D1 [S3]、 既存 tier1 lane 非侵襲、 0 件
grep -rn "\bTier1Lane\b" src/alpha_factory/graduation.py             # (13) Round D1 [S3]、 既存 Tier1Lane 非侵襲、 0 件
```

期待: T074 module は **既存 graduation 関連シンボル + collider bias 関連シンボルを 0 件参照** (= 純ライブラリ + 責務境界)。 tests は当該シンボルを mock 経由で扱う。

## 3. データモデル詳細 (擬似コード)

### 3.1 型 / 定数

```python
# src/alpha_factory/graduation.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Final, Literal


__all__ = [
    "GraduationTriggerStatus",
    "MultiPairAggregationKind",
    "MultiPairAggregationStatus",
    "GRADUATION_TRIGGER_MIN_GRADUATES",
    "GRADUATION_TRIGGER_MIN_EPOCHS",
    "GRADUATION_BATCH_PAIRS",
    "LANE_PARALLELISM",
    "GRADUATION_REPORT_SCHEMA_VERSION",
    "GRADUATION_TRIGGER_CALC_VERSION",
    "GRADUATION_AGGREGATION_CALC_VERSION",
    "GraduationEpochSummary",
    "GraduationArchiveSummary",
    "GraduationTriggerEvaluation",
    "MultiPairAggregationSketch",
    "evaluate_graduation_trigger",
    "compute_multi_pair_aggregation_sketch",
]


GraduationTriggerStatus = Literal[
    "ready",
    "insufficient_graduates",
    "insufficient_epochs",
    "no_recent_mission_pass",
]
MultiPairAggregationKind = Literal["worst_pair", "mean"]
MultiPairAggregationStatus = Literal["not_implemented"]


GRADUATION_TRIGGER_MIN_GRADUATES: Final[int] = 24
GRADUATION_TRIGGER_MIN_EPOCHS: Final[int] = 3
GRADUATION_BATCH_PAIRS: Final[frozenset[str]] = frozenset({
    "EUR_JPY", "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR",
})
LANE_PARALLELISM: Final[int] = 1

GRADUATION_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
GRADUATION_TRIGGER_CALC_VERSION: Final[str] = "v1"
GRADUATION_AGGREGATION_CALC_VERSION: Final[str] = "scaffold-v1"
```

### 3.2 GraduationEpochSummary (Round 3 [W1] 反映で issubset)

```python
@dataclass(frozen=True)
class GraduationEpochSummary:
    """1 epoch 単位の集約 (= 直近 N epoch mission_pass 判定の入力).

    SSOT (Round R2 [C1] [S1] / Round 3 [W1] 反映):
        observed_run_ids: この epoch の全観測 run (mission_pass / fail 問わず、 non-empty)
        mission_pass_run_ids: mission_pass を持つ run (= observed の subset、 空も許容)
        has_mission_pass property: bool(mission_pass_run_ids)

    invariant (Round 3 [W1] inclusive subset):
        observed_run_ids non-empty
        mission_pass_run_ids.issubset(observed_run_ids)   # = `<=` 演算、 真部分集合ではない
        (= 全 observed run が mission_pass の epoch も妥当: mission_pass == observed)
    """

    dataset_epoch_id: str
    observed_run_ids: frozenset[str]
    mission_pass_run_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.dataset_epoch_id:
            raise ValueError(
                f"GraduationEpochSummary.dataset_epoch_id must be non-empty"
            )
        if not self.observed_run_ids:
            raise ValueError(
                f"GraduationEpochSummary.observed_run_ids must be non-empty "
                f"(epoch_id={self.dataset_epoch_id!r})"
            )
        # Round 3 [W1]: issubset (inclusive) で SSOT
        if not self.mission_pass_run_ids.issubset(self.observed_run_ids):
            raise ValueError(
                f"GraduationEpochSummary.mission_pass_run_ids must be subset of observed_run_ids "
                f"(epoch_id={self.dataset_epoch_id!r}): "
                f"extra={self.mission_pass_run_ids - self.observed_run_ids}"
            )

    @property
    def has_mission_pass(self) -> bool:
        """Round R2 [C1]: mission pass run の有無で導出."""
        return bool(self.mission_pass_run_ids)
```

### 3.3 GraduationArchiveSummary (Round 3 [S1] [W2] [W4] 反映)

```python
@dataclass(frozen=True)
class GraduationArchiveSummary:
    """archive read-only の評価時点 snapshot 集計 (caller responsibility).

    SSOT:
        n_graduates: archive 内 graduated=True の評価時点 snapshot count (Round R1 [W6])
        distinct_dataset_epoch_ids: archive 内 distinct dataset_epoch_id 集合 (空集合許容)
        recent_epoch_summaries: 直近 N+ epoch の GraduationEpochSummary 列
            **新しい順、 [0] が active/current、 以降古い epoch へ進む** (Round 3 [S1] 表現)
            epoch 単位 unique
        archive_epoch_id_active: str | None (Round R2 [C2])
            None = empty archive (= distinct 空 + recent 空)
            non-None = active epoch あり (= [0]==active 一致 invariant)

    Phase 2 adapter contract (Round 3 [W2] [W4]):
        - 同一 archive snapshot から単一 transaction で構築 (Round R2 [W3])
        - 「active epoch はあるが recent_epoch_summaries 未構築」 中間状態は本 contract 範囲外 (= 別 TODO)
        - recent_epoch_summaries[1:] の順序正当性 (= 古い順) は __post_init__ で検出不能、 Phase 2 adapter test 責務
    """

    n_graduates: int
    distinct_dataset_epoch_ids: frozenset[str]
    recent_epoch_summaries: tuple[GraduationEpochSummary, ...]
    archive_epoch_id_active: str | None

    def __post_init__(self) -> None:
        # **順序仕様 (Round D1 [W2] 反映)**: I-1 → I-2 → I-3 → I-4
        # 各 invariant は前段の検証通過を前提とし、 順序依存で raise message が一意.

        # I-1: n_graduates >= 0
        if self.n_graduates < 0:
            raise ValueError(f"n_graduates >= 0 required, got {self.n_graduates}")

        # I-2: recent_epoch_summaries の epoch 単位ユニーク性
        seen_epoch_ids: set[str] = set()
        for s in self.recent_epoch_summaries:
            if s.dataset_epoch_id in seen_epoch_ids:
                raise ValueError(
                    f"recent_epoch_summaries duplicate dataset_epoch_id: {s.dataset_epoch_id!r}"
                )
            seen_epoch_ids.add(s.dataset_epoch_id)

        # I-3: 全 recent[i].dataset_epoch_id ∈ distinct_dataset_epoch_ids
        for s in self.recent_epoch_summaries:
            if s.dataset_epoch_id not in self.distinct_dataset_epoch_ids:
                raise ValueError(
                    f"recent_epoch_summaries[{s.dataset_epoch_id!r}] not in "
                    f"distinct_dataset_epoch_ids ({sorted(self.distinct_dataset_epoch_ids)})"
                )

        # I-4: archive_epoch_id_active 整合 (Round R2 [C2] / Round 3 [W4])
        if self.archive_epoch_id_active is None:
            # empty archive case
            if self.distinct_dataset_epoch_ids:
                raise ValueError(
                    f"archive_epoch_id_active=None requires empty distinct_dataset_epoch_ids, "
                    f"got {sorted(self.distinct_dataset_epoch_ids)}"
                )
            if self.recent_epoch_summaries:
                raise ValueError(
                    f"archive_epoch_id_active=None requires empty recent_epoch_summaries, "
                    f"got len={len(self.recent_epoch_summaries)}"
                )
        else:
            # non-None case
            if self.archive_epoch_id_active not in self.distinct_dataset_epoch_ids:
                raise ValueError(
                    f"archive_epoch_id_active={self.archive_epoch_id_active!r} not in "
                    f"distinct_dataset_epoch_ids"
                )
            if self.recent_epoch_summaries:
                head = self.recent_epoch_summaries[0]
                if head.dataset_epoch_id != self.archive_epoch_id_active:
                    raise ValueError(
                        f"recent_epoch_summaries[0].dataset_epoch_id ({head.dataset_epoch_id!r}) "
                        f"!= archive_epoch_id_active ({self.archive_epoch_id_active!r})"
                    )
        # 注: recent_epoch_summaries[1:] の順序正当性 (= 古い順) は __post_init__ で検出不能.
        #     Phase 2 adapter test の責務 (Round 3 [W2]).
```

### 3.4 GraduationTriggerEvaluation (Round 3 [W3] docstring 強化)

```python
@dataclass(frozen=True)
class GraduationTriggerEvaluation:
    """3 条件判定結果.

    SSOT (synthesis § 11.1 / Round R2 [W2] / Round 3 [W3]):
        status と数値 field の disjoint 整合.
        has_recent_mission_pass は **trigger status 上の成立フラグ** (Round 3 [W3]):
            status="ready"     → True (= 全 3 条件達成)
            status != "ready"  → False (= 早期 return 時、 実データ独立評価ではない)

    優先順位 (disjoint):
        1. n_graduates < 24                                    → "insufficient_graduates"
        2. distinct epoch < 3                                  → "insufficient_epochs"
        3. 直近 N epoch すべてで has_mission_pass を満たさない   → "no_recent_mission_pass"
        4. 全達成                                                → "ready"
    """

    status: GraduationTriggerStatus
    n_graduates: int                                        # snapshot count、 status 関わらず実測値
    n_distinct_epochs: int                                  # 実測値
    recent_mission_pass_epoch_ids: tuple[str, ...]          # status="ready" のみ完全集計、 他は空 tuple
    has_recent_mission_pass: bool                            # status 従属、 docstring 固定 (Round 3 [W3])
    recent_epochs_required: int                              # caller 引数値の audit
    calc_version: str                                        # = GRADUATION_TRIGGER_CALC_VERSION

    def __post_init__(self) -> None:
        # 順序仕様 (Round D1 [W2] [C1] / Round D3 [W1] 反映): I-1 → I-2 → I-2b (cross-field) → I-3 status 別
        # I-1: calc_version
        if self.calc_version != GRADUATION_TRIGGER_CALC_VERSION:
            raise ValueError(
                f"calc_version must be {GRADUATION_TRIGGER_CALC_VERSION!r}, got {self.calc_version!r}"
            )
        # I-2: 実測値範囲
        if self.n_graduates < 0:
            raise ValueError(f"n_graduates >= 0 required, got {self.n_graduates}")
        if self.n_distinct_epochs < 0:
            raise ValueError(f"n_distinct_epochs >= 0 required, got {self.n_distinct_epochs}")
        # Round D1 [C1] 反映: dataclass 直接構築でも recent_epochs_required >= 1 を invariant 化
        if self.recent_epochs_required < 1:
            raise ValueError(f"recent_epochs_required >= 1 required, got {self.recent_epochs_required}")

        # I-2b: cross-field invariant (Round D3 [W1] 反映)
        # duplicate 禁止
        if len(set(self.recent_mission_pass_epoch_ids)) != len(self.recent_mission_pass_epoch_ids):
            raise ValueError(
                f"recent_mission_pass_epoch_ids must be unique, got duplicates in "
                f"{self.recent_mission_pass_epoch_ids}"
            )
        # mission pass epoch は distinct epoch の subset (= n_distinct_epochs >= len(unique mission pass))
        if self.n_distinct_epochs < len(self.recent_mission_pass_epoch_ids):
            raise ValueError(
                f"n_distinct_epochs ({self.n_distinct_epochs}) >= len(recent_mission_pass_epoch_ids) "
                f"({len(self.recent_mission_pass_epoch_ids)}) required (mission pass epochs ⊆ distinct epochs)"
            )

        # I-3: status 別 invariant (Round 3 [W3] / Round D1 [W3] 完全網羅、 recent_mission_pass_epoch_ids 真偽式まで)
        n_recent = len(self.recent_mission_pass_epoch_ids)
        if self.status == "ready":
            if self.n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    f"status='ready' requires n_graduates >= {GRADUATION_TRIGGER_MIN_GRADUATES}, "
                    f"got {self.n_graduates}"
                )
            if self.n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS:
                raise ValueError(
                    f"status='ready' requires n_distinct_epochs >= {GRADUATION_TRIGGER_MIN_EPOCHS}, "
                    f"got {self.n_distinct_epochs}"
                )
            if n_recent != self.recent_epochs_required:
                raise ValueError(
                    f"status='ready' requires len(recent_mission_pass_epoch_ids) == "
                    f"recent_epochs_required ({self.recent_epochs_required}), got {n_recent}"
                )
            if not self.has_recent_mission_pass:
                raise ValueError("status='ready' requires has_recent_mission_pass == True")
        elif self.status == "insufficient_graduates":
            if self.n_graduates >= GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    f"status='insufficient_graduates' requires n_graduates < "
                    f"{GRADUATION_TRIGGER_MIN_GRADUATES}, got {self.n_graduates}"
                )
            if n_recent != 0:
                raise ValueError(
                    f"status='insufficient_graduates' requires recent_mission_pass_epoch_ids "
                    f"empty (early return), got len={n_recent}"
                )
            if self.has_recent_mission_pass:
                raise ValueError("status='insufficient_graduates' requires has_recent_mission_pass == False")
        elif self.status == "insufficient_epochs":
            if self.n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    f"status='insufficient_epochs' implies graduates condition OK, "
                    f"got n_graduates={self.n_graduates}"
                )
            if self.n_distinct_epochs >= GRADUATION_TRIGGER_MIN_EPOCHS:
                raise ValueError(
                    f"status='insufficient_epochs' requires n_distinct_epochs < "
                    f"{GRADUATION_TRIGGER_MIN_EPOCHS}, got {self.n_distinct_epochs}"
                )
            if n_recent != 0:
                raise ValueError(
                    f"status='insufficient_epochs' requires recent_mission_pass_epoch_ids empty, got len={n_recent}"
                )
            if self.has_recent_mission_pass:
                raise ValueError("status='insufficient_epochs' requires has_recent_mission_pass == False")
        elif self.status == "no_recent_mission_pass":
            # Round D2 [W1]: partial pass diagnostic 許容
            #   recent_mission_pass_epoch_ids は **実測値** (= 直近 N epoch のうち実際に pass した ids)
            #   "no_recent_mission_pass" は「N 個中 N 未満」 を表現 (= 0..N-1 個 pass)
            #   早期 return (= recent_epoch_summaries が required 未満) も含む
            if self.n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    f"status='no_recent_mission_pass' implies graduates condition OK, got n_graduates={self.n_graduates}"
                )
            if self.n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS:
                raise ValueError(
                    f"status='no_recent_mission_pass' implies epochs condition OK, got n_distinct_epochs={self.n_distinct_epochs}"
                )
            # Round D2 [W1]: 0 <= len < required (= partial pass 許容)
            if not (0 <= n_recent < self.recent_epochs_required):
                raise ValueError(
                    f"status='no_recent_mission_pass' requires "
                    f"0 <= len(recent_mission_pass_epoch_ids) < recent_epochs_required "
                    f"({self.recent_epochs_required}), got len={n_recent}"
                )
            if self.has_recent_mission_pass:
                raise ValueError("status='no_recent_mission_pass' requires has_recent_mission_pass == False")
        else:
            raise ValueError(f"unknown GraduationTriggerStatus: {self.status!r}")
```

### 3.5 MultiPairAggregationSketch (T073 SSOT 継承)

```python
@dataclass(frozen=True)
class MultiPairAggregationSketch:
    """multi-pair 集約 scaffold (Phase 4 で実装).

    Phase 4 robust 系追加禁止規範 (Round 3 [S4]):
        synthesis § 11.2 確定値 = worst_pair / mean のみ.
        robust 系 (= worst-case CVaR 等) は **synthesis 改訂前に MultiPairAggregationKind Literal に追加禁止**.
        Phase 4 で実装する場合は synthesis Round 22 改訂で worst_pair / mean 以外を確定後、 Literal 拡張.
    """
    kind: MultiPairAggregationKind
    status: MultiPairAggregationStatus    # = "not_implemented" 固定
    calc_version: str                      # = "scaffold-v1"

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(
                f"MultiPairAggregationSketch.status must be 'not_implemented', got {self.status!r}"
            )
        if self.calc_version != GRADUATION_AGGREGATION_CALC_VERSION:
            raise ValueError(
                f"calc_version must be {GRADUATION_AGGREGATION_CALC_VERSION!r}, got {self.calc_version!r}"
            )
```

## 4. アルゴリズム詳細 (擬似コード)

### 4.1 evaluate_graduation_trigger

```python
def evaluate_graduation_trigger(
    *,
    archive_summary: GraduationArchiveSummary,
    recent_epochs_with_mission_pass_required: int,
) -> GraduationTriggerEvaluation:
    """archive read-only で 3 条件判定 (synthesis § 11.1).

    Phase 2 adapter responsibility (Round 3 [S2]):
        config キー `graduation.recent_epochs_with_mission_pass_required` から caller が値を渡す.
        config missing 時は caller が ValueError raise (= 暗黙 default 不可、 fail-closed).

    優先順位 (disjoint):
        1. n_graduates < 24                                 → "insufficient_graduates"
        2. distinct epoch < 3                               → "insufficient_epochs"
        3. 直近 N epoch すべてで has_mission_pass 不充足    → "no_recent_mission_pass"
        4. 全達成                                            → "ready"

    Raises:
        ValueError: recent_epochs_with_mission_pass_required < 1.
    """
    if recent_epochs_with_mission_pass_required < 1:
        raise ValueError(
            f"recent_epochs_with_mission_pass_required >= 1 required, "
            f"got {recent_epochs_with_mission_pass_required}"
        )

    n_graduates = archive_summary.n_graduates
    n_distinct_epochs = len(archive_summary.distinct_dataset_epoch_ids)
    n_required = recent_epochs_with_mission_pass_required

    # Step 1: graduates 不足 (最優先)
    if n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
        return _make_trigger(
            status="insufficient_graduates",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=tuple(),
            recent_epochs_required=n_required,
        )

    # Step 2: epoch 不足
    if n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS:
        return _make_trigger(
            status="insufficient_epochs",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=tuple(),
            recent_epochs_required=n_required,
        )

    # Step 3: 直近 N epoch 連続 mission_pass 判定
    recent = archive_summary.recent_epoch_summaries[:n_required]
    if len(recent) < n_required:
        return _make_trigger(
            status="no_recent_mission_pass",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=tuple(),
            recent_epochs_required=n_required,
        )

    mission_pass_epoch_ids = tuple(
        e.dataset_epoch_id for e in recent if e.has_mission_pass
    )
    if len(mission_pass_epoch_ids) < n_required:
        # Round D2 [W1]: partial pass diagnostic を保持 (= 実測値で「N 中何個 pass か」 を caller に提示)
        return _make_trigger(
            status="no_recent_mission_pass",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=mission_pass_epoch_ids,    # partial pass 保持
            recent_epochs_required=n_required,
        )

    # Step 4: 全達成
    return _make_trigger(
        status="ready",
        n_graduates=n_graduates,
        n_distinct_epochs=n_distinct_epochs,
        recent_mission_pass_epoch_ids=mission_pass_epoch_ids,
        recent_epochs_required=n_required,
    )


def _make_trigger(
    *,
    status: GraduationTriggerStatus,
    n_graduates: int,
    n_distinct_epochs: int,
    recent_mission_pass_epoch_ids: tuple[str, ...],
    recent_epochs_required: int,
) -> GraduationTriggerEvaluation:
    """Round 3 [W3] 反映: has_recent_mission_pass は status 従属 (= status="ready" のみ True)."""
    has_pass = (status == "ready")
    return GraduationTriggerEvaluation(
        status=status,
        n_graduates=n_graduates,
        n_distinct_epochs=n_distinct_epochs,
        recent_mission_pass_epoch_ids=recent_mission_pass_epoch_ids,
        has_recent_mission_pass=has_pass,
        recent_epochs_required=recent_epochs_required,
        calc_version=GRADUATION_TRIGGER_CALC_VERSION,
    )
```

### 4.2 compute_multi_pair_aggregation_sketch

```python
def compute_multi_pair_aggregation_sketch(
    *,
    kind: MultiPairAggregationKind,
    calc_version: str = GRADUATION_AGGREGATION_CALC_VERSION,
) -> MultiPairAggregationSketch:
    return MultiPairAggregationSketch(
        kind=kind,
        status="not_implemented",
        calc_version=calc_version,
    )
```

## 5. テスト計画 (詳細)

### 5.0 命名規約

`Fxxx_<behavior>` 形式で pytest 関数名と 1:1 対応。

### 5.1 `tests/alpha_factory/test_graduation.py` (新規)

#### F1-F3: 定数 / Literal tests

| test_id | 内容 | pytest 関数名 |
|---|---|---|
| F1_constants | 定数値が SSOT 一致 (= 24 / 3 / 6 pair frozenset / LANE_PARALLELISM=1 / version 文字列) | `test_graduation_constants_match_ssot` |
| F2_status_values | GraduationTriggerStatus 4 値 / MultiPairAggregationStatus 1 値 / MultiPairAggregationKind 2 値 | `test_graduation_status_literal_values` |
| F3_batch_pairs_frozenset | GRADUATION_BATCH_PAIRS が frozenset、 順序非依存等価 | `test_graduation_batch_pairs_is_frozenset` |

#### F4-F8: GraduationEpochSummary tests (Round 3 [W1] issubset)

| F4_observed_non_empty | observed_run_ids=frozenset() → ValueError | `test_epoch_summary_observed_non_empty` |
| F5_dataset_epoch_id_non_empty | dataset_epoch_id="" → ValueError | `test_epoch_summary_dataset_epoch_id_non_empty` |
| F6_mission_pass_subset | mission_pass_run_ids ⊄ observed_run_ids → ValueError | `test_epoch_summary_mission_pass_must_be_subset` |
| F6b_mission_pass_full_inclusive | mission_pass_run_ids == observed_run_ids → 正常 (Round 3 [W1]、 inclusive subset) | `test_epoch_summary_mission_pass_equal_observed_allowed` |
| F7_has_mission_pass_property | mission_pass_run_ids non-empty → has_mission_pass=True、 空 → False | `test_epoch_summary_has_mission_pass_property` |
| F8_frozen_eq_hash | 同 instance (= 同 epoch_id / observed / mission_pass) で eq/hash 等価 | `test_epoch_summary_frozen_eq_hash` |

#### F9-F14: GraduationArchiveSummary tests

| F9_n_graduates_non_negative | n_graduates=-1 → ValueError | `test_archive_summary_n_graduates_non_negative` |
| F10_recent_summaries_unique_epoch | recent_epoch_summaries で同 dataset_epoch_id 重複 → ValueError | `test_archive_summary_recent_summaries_unique_epoch` |
| F11_recent_summaries_in_distinct | recent[i].dataset_epoch_id ∉ distinct_dataset_epoch_ids → ValueError | `test_archive_summary_recent_in_distinct` |
| F12_active_none_empty_archive | archive_epoch_id_active=None / distinct=空 / recent=空 → 正常 | `test_archive_summary_active_none_empty` |
| F12b_active_none_with_distinct | archive_epoch_id_active=None + distinct 非空 → ValueError | `test_archive_summary_active_none_requires_empty_distinct` |
| F12c_active_none_with_recent | archive_epoch_id_active=None + recent 非空 → ValueError | `test_archive_summary_active_none_requires_empty_recent` |
| F13_active_in_distinct | archive_epoch_id_active ∉ distinct_dataset_epoch_ids → ValueError | `test_archive_summary_active_must_be_in_distinct` |
| F14_active_matches_recent_head | recent[0].dataset_epoch_id != archive_epoch_id_active → ValueError | `test_archive_summary_active_matches_recent_head` |

#### F15-F22: evaluate_graduation_trigger tests

| F15_happy_path_ready | 全 3 条件達成 → status="ready" / has_recent_mission_pass=True | `test_evaluate_trigger_happy_path_ready` |
| F16_insufficient_graduates | n_graduates=23 → status="insufficient_graduates" | `test_evaluate_trigger_insufficient_graduates` |
| F17_insufficient_epochs | distinct=2 → status="insufficient_epochs" | `test_evaluate_trigger_insufficient_epochs` |
| F18_no_recent_mission_pass_short | recent_epoch_summaries が required 未満 → status="no_recent_mission_pass" | `test_evaluate_trigger_no_recent_mission_pass_short` |
| F19_no_recent_mission_pass_partial | 直近 N epoch 中 1 epoch のみ has_mission_pass → status="no_recent_mission_pass" | `test_evaluate_trigger_no_recent_mission_pass_partial` |
| F20_priority_graduates_over_epochs | n_graduates=23 + distinct=2 → "insufficient_graduates" (= 最優先) | `test_evaluate_trigger_priority_graduates_over_epochs` |
| F21_priority_epochs_over_recent | n_graduates=24 + distinct=2 + recent OK → "insufficient_epochs" | `test_evaluate_trigger_priority_epochs_over_recent` |
| F22_required_lt_one_raises | recent_epochs_with_mission_pass_required=0 → ValueError | `test_evaluate_trigger_required_lt_one_raises` |
| F22b_required_caller_argument | required を 1 / 2 / 3 で渡して結果が引数依存に変わる (= 定数化していない、 Round R1 [C1]) | `test_evaluate_trigger_required_is_caller_argument` |
| F22c_has_recent_mission_pass_status_dependent | status != "ready" 時の has_recent_mission_pass=False (Round 3 [W3]) | `test_evaluate_trigger_has_recent_mission_pass_status_dependent` |
| F22d_dataclass_required_lt_one | GraduationTriggerEvaluation を直接構築して recent_epochs_required=0 → ValueError (Round D1 [C1]、 dataclass invariant) | `test_trigger_evaluation_dataclass_required_lt_one_raises` |
| F22e_status_invariant_complete | 各 status 別の数値 field disjoint invariant 違反 → ValueError (Round D1 [W3]、 Round D2 [S3] pytest parametrize、 4 status × invariant 違反 4 field の matrix) | `test_trigger_evaluation_status_invariant_complete[parametrize]` |
| F22f_partial_pass_zero | Round D2 [W1] / Round D3 [S3]: status="no_recent_mission_pass" + len=0 → 正常 (= 全 fail) | `test_trigger_no_recent_mission_pass_partial_zero` |
| F22f_partial_pass_max | Round D3 [S3]: status="no_recent_mission_pass" + len=required-1 → 正常 (= partial 最大値) | `test_trigger_no_recent_mission_pass_partial_max` |
| F22g_full_pass_invalid | Round D2 [W1]: status="no_recent_mission_pass" + len=required → ValueError (= ready のはず) | `test_trigger_no_recent_mission_pass_full_pass_invalid` |
| F22g_overflow_invalid | Round D3 [S3]: status="no_recent_mission_pass" + len>required → ValueError (= 0 <= len < required 違反) | `test_trigger_no_recent_mission_pass_overflow_invalid` |
| F22h_duplicate_epoch_ids | Round D3 [W1]: recent_mission_pass_epoch_ids に duplicate → ValueError | `test_trigger_evaluation_duplicate_epoch_ids_invalid` |
| F22i_n_distinct_epochs_lt_recent_pass | Round D3 [W1]: n_distinct_epochs < len(recent_mission_pass_epoch_ids) → ValueError | `test_trigger_evaluation_n_distinct_epochs_lt_recent_pass_invalid` |
| F22j_ready_n_distinct_lt_required | Round D3 [W1]: status="ready" + n_distinct_epochs < recent_epochs_required → ValueError (= 上記 I-2b cross-field invariant の派生) | `test_trigger_evaluation_ready_n_distinct_lt_required_invalid` |

#### F23-F25: MultiPairAggregationSketch / scaffold tests

| F23_pbo_scaffold_factory | compute_multi_pair_aggregation_sketch(kind="worst_pair") → status="not_implemented" / calc_version="scaffold-v1" | `test_compute_multi_pair_aggregation_sketch_factory` |
| F24_kind_mean | kind="mean" → 同上 | `test_compute_multi_pair_aggregation_sketch_kind_mean` |
| F25_scaffold_no_raise | scaffold 関数は NotImplementedError raise しない | `test_multi_pair_aggregation_sketch_does_not_raise` |
| F25b_status_invalid | status="ok" → ValueError | `test_multi_pair_aggregation_sketch_status_invalid` |
| F25c_calc_version_invalid | calc_version="v1" → ValueError | `test_multi_pair_aggregation_sketch_calc_version_invalid` |

#### F26-F27: 既存 SSOT 整合 / collider bias tests

| F26_t064_set_equal | GRADUATION_BATCH_PAIRS == frozenset({STAGE_C_ANCHOR_PAIR} ∪ STAGE_C_SHADOW_PAIR_LIST) (= test 側のみ T064 import、 Round R2 [S4]) | `test_graduation_batch_pairs_set_equal_to_t064` |
| F27_no_collider_bias_imports | T074 module 内に observability_flags / holiday / DST 参照なし (Round 3 [S3] / Round D2 [W2] [W3] / Round D3 [W2] [W3] AST 解析 + 完全一致 + substring 分離) | `test_graduation_module_no_collider_bias_imports` |
| F27_relative_import_alias | Round D3 [W3]: `from . import archive` の検出 (= ImportFrom alias.name 経由)、 mock module で raise 確認 | `test_graduation_module_grep_dod_detects_relative_import_alias` |
| F27_substring_case_sensitive | Round D3 [W4]: forbidden_substrings は case-sensitive (= "DST" 大文字 substring は検出、 "dst_xxx" 小文字は許容) を test で固定 | `test_graduation_module_grep_dod_substring_case_sensitive` |
| F27_tier1_substring_allowed | Round D3 [W2]: `tier1_event` のような substring は許容、 `tier1` (exact name) のみ reject | `test_graduation_module_grep_dod_tier1_substring_allowed` |

### 5.2 grep DoD test 化 (Round 3 [S3] / Round D1 [W7] / Round D2 [W2] [W3] AST ベース)

Round D1 [W7] / Round D2 [W2] [W3] 反映:
- substring grep は docstring / comment 内 false positive 排除 (AST 解析)
- string literal (= ast.Constant(str)) も検出対象に追加 (Round D2 [W2])
- ただし docstring (= ast.Module / FunctionDef / ClassDef の最初の statement) は除外
- forbidden 識別子は **完全一致 (exact name)** + **substring** を分離 (Round D2 [W3])、 false positive 排除

```python
def test_graduation_module_no_existing_swim_lane_archive_imports():
    """Round 3 [S3] / Round D1 [W7] / Round D2 [W2] [W3] 反映:
    AST 解析で docstring 除外、 import statement / Name / Attribute / string literal 検証.
    forbidden 識別子は exact match と substring を分離 (= false positive 排除).
    """
    import ast
    import src.alpha_factory.graduation as g

    with open(g.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # docstring node 集合 (= 除外対象、 ast.Module / FunctionDef / ClassDef の最初の statement)
    docstring_nodes: set[int] = set()
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(parent, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))

    # 1. forbidden module (import 経路、 Round R2 [S3])
    forbidden_modules_substrings = ("archive", "swim_lane", "cross_pair")
    # 2. forbidden exact name (Round D2 [W3] / Round D3 [W2] 完全一致)
    # 注: tier1 / tier_1 は exact name のみ reject、 `tier1_event` のような派生 identifier は許容
    # (= 設計選択、 将来 T074 内で tier1 概念を扱う場合の柔軟性確保)
    forbidden_exact_names = (
        "ANCHOR_PAIRS",
        "promote_graduates",
        "mark_graduated",
        "GraduationLane",
        "seed_graduates",
        "Tier1Lane",
        "tier1",        # exact name (= identifier 'tier1' そのもの)
        "tier_1",
    )
    # 3. forbidden substring (Round D3 [W4] 反映、 case-sensitive substring match)
    # 注: case-sensitive (= "DST" 大文字を要求、 "dst_xxx" は検出されない)
    #     T074 module で `dst_xxx` 等の小文字経路を許容、 大文字 "DST" のみ collider bias mark を検出
    forbidden_substrings = ("holiday", "DST", "observability_flags")

    def _check_string_token(token: str, context: str) -> None:
        assert token not in forbidden_exact_names, (
            f"T074 module references forbidden exact name {token!r} ({context})"
        )
        for sub in forbidden_substrings:
            assert sub not in token, (
                f"T074 module references identifier containing {sub!r} ({context}): {token!r}"
            )

    # ImportFrom / Import check (Round D3 [W3] 反映で `from . import archive` も検出)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # node.module は `from X import Y` の X 部分 (= None なら relative import)
            if node.module:
                for sub in forbidden_modules_substrings:
                    assert sub not in node.module, (
                        f"T074 module imports forbidden module {node.module!r} "
                        f"(matched substring {sub!r})"
                    )
            # alias.name も検査 (= `from . import archive` で alias.name == "archive")
            for alias in node.names:
                for sub in forbidden_modules_substrings:
                    assert sub not in alias.name, (
                        f"T074 module ImportFrom alias {alias.name!r} matched {sub!r}"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for sub in forbidden_modules_substrings:
                    assert sub not in alias.name, (
                        f"T074 module Import {alias.name!r} matched {sub!r}"
                    )

    # Name / Attribute check
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            _check_string_token(node.id, f"Name at line {node.lineno}")
        elif isinstance(node, ast.Attribute):
            _check_string_token(node.attr, f"Attribute at line {node.lineno}")

    # string literal (Round D2 [W2])、 docstring 除外
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_nodes:
                continue   # docstring 除外
            _check_string_token(node.value, f"string literal at line {node.lineno}")
```

## 6. 失敗モード / fail-closed 経路

| ID | 失敗パターン | 対応 |
|---|---|---|
| FC1 | GraduationEpochSummary.observed_run_ids=空 | __post_init__ ValueError |
| FC2 | mission_pass_run_ids ⊄ observed_run_ids | __post_init__ ValueError (Round 3 [W1] issubset) |
| FC3 | dataset_epoch_id="" | __post_init__ ValueError |
| FC4 | n_graduates < 0 | __post_init__ ValueError |
| FC5 | recent_epoch_summaries の epoch 単位重複 | __post_init__ ValueError |
| FC6 | recent[i].dataset_epoch_id ∉ distinct | __post_init__ ValueError |
| FC7 | archive_epoch_id_active=None と distinct/recent の整合違反 | __post_init__ ValueError (Round R2 [C2]) |
| FC8 | archive_epoch_id_active != recent[0].dataset_epoch_id | __post_init__ ValueError |
| FC9 | recent_epochs_with_mission_pass_required < 1 | evaluate_graduation_trigger ValueError |
| FC10 | GraduationTriggerEvaluation の status と数値 field の disjoint 違反 | __post_init__ ValueError |
| FC11 | MultiPairAggregationSketch の status / calc_version 違反 | __post_init__ ValueError |
| FC12 | Phase 2 caller (run_ga.py) で config `graduation.recent_epochs_with_mission_pass_required` missing | caller (= 別 PR) ValueError raise (Round 3 [S2]) |

## 7. backward-compat 互換性 (4 面)

T074 PR は新規 module 追加のみで既存ファイル touch なし。

### 7.1 constructor 互換 / 7.2 eq/hash 互換 / 7.3 serialization / 7.4 既存 fixture
全て影響なし (= 新規 module 追加のみ)。 既存 caller (= swim_lane / archive / cross_pair 経由) には touch しない。

## 8. DoD (Definition of Done)

T074 PR が完了するための最小条件:

### 8.1 実装完了

- [ ] `src/alpha_factory/graduation.py` 新規、 § 3 / § 4 全関数 + 全 dataclass + 全定数実装
- [ ] `mission_pass_run_ids.issubset(observed_run_ids)` (Round 3 [W1]、 inclusive subset)
- [ ] `archive_epoch_id_active: str | None` で empty archive 業務不足扱い (Round R2 [C2])
- [ ] `recent_epoch_summaries` は recent-first head N 順 (= 新しい順、 [0] active)
- [ ] `has_recent_mission_pass` は status 従属 (Round 3 [W3])
- [ ] `_make_trigger` keyword-only call

### 8.2 テスト

- [ ] `tests/alpha_factory/test_graduation.py` 新規、 § 5 全 test pass (= F1-F27)
- [ ] mypy / ruff pass
- [ ] grep DoD test 化 (F27、 10 検索語、 Round 3 [S3])

### 8.3 互換性 / 監査

- [ ] **C2 parallel-path grep DoD** 実行 (Round 3 [S3]、 10 検索語):
  - graduation.py を src/ から import する経路 0 件 (= tests のみ)
  - 既存 swim_lane / archive / cross_pair / observability_flags / promote_graduates / mark_graduated / GraduationLane / ANCHOR_PAIRS / holiday / DST 参照なし
- [ ] PR description に **collider bias 規範テンプレート** (= T072 / T073 継承) を Phase 2 申し送りとして明記
- [ ] PR description に **adapter contract** (Round R2 [W3]) を Phase 2 run_ga.py 改訂申し送りとして明記:
  > Phase 2 で run_ga.py を唯一の SSOT adapter とし、 同一 archive snapshot から単一 transaction で集計。 `graduation.recent_epochs_with_mission_pass_required` config キー missing 時は ValueError raise (= 暗黙 default 不可、 Round 3 [S2])。

### 8.4 collider bias 規範テンプレート (PR description 用、 T072 / T073 継承)

```markdown
## T074 collider bias 回避規範 (Phase 2 申し送り、 T071 経由)

T074 graduation lane scaffold は **collider bias 判定を行わない**。 holiday_markets / dst_transition_markets /
schedule_status の stratified audit は **Phase 2 で T071 RunObservabilityReport 経由** で出力する責務。
T074 module は observability_flags を参照しない (= grep DoD で確認、 Round 3 [S3])。

### Fact (= T074 SSOT)
- evaluate_graduation_trigger は archive read-only で 3 条件判定のみ
- GraduationArchiveSummary 入力には holiday_markets 等の flag を含めない
- T074 module は src/alpha_factory/{archive,swim_lane,cross_pair}.py を import しない
- multi-pair 集約は scaffold のみ、 Phase 4 で synthesis 改訂前に robust 系 Literal 追加禁止 (Round 3 [S4])

### Phase 2 申し送り
- T071 RunObservabilityReport.graduation_trigger field 配線時に stratified audit 経路を別途確保
- run_ga.py adapter で archive read-only 集計 + config fail-closed
```

## 9. Phase 1 / Phase 2 / Phase 4 切り分け

### 9.1 Phase 1 (T074 PR、 純ライブラリ)

§ 1.1 全範囲。 単体テストのみで runtime 未組込 (= Phase 1 共通原則)。

### 9.2 Phase 2 (別 TODO、 cascade port 切替時)

- T071 RunObservabilityReport.graduation_trigger field 追加
- run_ga.py 唯一の SSOT adapter (Round R2 [W3] 同一 snapshot transaction、 Round 3 [S2] config fail-closed)
- collider bias 規範を T071 経由で stratified audit 出力

#### Phase 2 adapter contract 最小契約 (Round D1 [W8] 反映)

Phase 2 で run_ga.py の archive read-only 集計 helper の契約:

| 項目 | 契約 |
|---|---|
| 入力 snapshot 条件 | archive snapshot は **単一 transaction 内で確定** (= 評価開始から終了まで mutation 不可、 caller 責務で snapshot lock or copy)。 mutation 検出時は ValueError raise |
| 出力 summary 一貫性 | n_graduates / distinct_dataset_epoch_ids / recent_epoch_summaries / archive_epoch_id_active は全て同一 snapshot から構築、 read 時刻が異なる field は禁止 (= 連続 read 揺らぎ排除) |
| 失敗時 raise 規約 | snapshot mutation 検出 / archive 不整合 (= graduated=True かつ dataset_epoch_id missing 等) は ValueError raise (= silent skip 禁止)、 caller (= run_ga.py 上位) で fail-closed |
| config missing | `graduation.recent_epochs_with_mission_pass_required` キー不在は ValueError raise (Round 3 [S2]、 暗黙 default 不可) |
| ロールバック | adapter 内部状態は immutable build (= dataclass frozen 経由)、 build 失敗時は exception 経由でロールバック (= 部分構築 GraduationArchiveSummary を返さない) |

**Round D2 [W4] / Round D3 [S1] 反映**: 既存 `archive.py` に **transaction / snapshot API が無い場合** は、 Phase 2 PR で以下のいずれかを追加実装する責務:
- **案 A (推奨)**: `archive.py` に `snapshot_for_graduation_audit() -> ArchiveSnapshotDTO` メソッド追加 (= immutable DTO 経由)
- **案 B (次点)**: archive 全 read を `with archive.transaction():` で囲む context manager 追加 (= 既存 archive.py 改造)
- **案 C (production 非推奨)**: caller (run_ga.py) で archive 全 read を 1 関数内で完結、 OS 経路で別 process が archive 書込しない前提を SSOT 化 (= 簡易、 production では非推奨、 test/debug 限定)

**推奨順 SSOT**: 案 A > 案 B > 案 C (Round D3 [S1])。 Phase 2 詳細設計で原則 案 A、 archive.py 改造範囲が大きい場合のみ案 B。 Phase 1 (T074 PR) は申し送りのみで実装しない。

詳細は Phase 2 PR で T071 詳細設計改訂と同時に確定。 T074 PR では本契約を **PR description + Phase 2 申し送り** として記録。

### 9.3 Phase 4 (別 TODO、 multi-pair 集約実装)

- compute_multi_pair_aggregation_sketch を実装版に置換
- GraduationBatchInput / GraduationBatchReport dataclass 導入
- GraduationLane.run_generation の実装
- GRADUATION_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 (MINOR bump)
- robust 系 aggregation は **`synthesis_schema_version >= 22` まで MultiPairAggregationKind Literal 追加禁止** (Round 3 [S4] / Round D1 [S2] / Round D2 [S2] / Round D3 [S2] 反映)
  - **synthesis Round 22 改訂 PR で `synthesis_schema_version: 22` を明示追加** することを synthesis 詳細設計改訂申し送りに含める (Round D3 [S2])
  - 既存 synthesis 文書 (`devnotes/20260428-2300-cascade-port-debate/synthesis.md`) に schema_version field が無い場合、 Round 22 改訂 PR が **schema_version 化を同時実施** (= 旧 1-21 round は schema_version=21 を遡及付与 or 不在許容)
  - 単一 schema_version 値で判定可能 (= 複数 PR でも整合)

## 10. 参考文献

T074 Phase 1 は学術文献依存なし。 Phase 4 で multi-pair 集約実装時に以下を参照:
- Bailey, D. H., Borwein, J. M., López de Prado, M. M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* (= multi-pair 集約 + graduation 判定品質管理)
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability.* (= multi-pair 検定)
- Kim, W., Kim, J. H., & Fabozzi, F. J. (2018). *Robust Portfolio Optimization: A Survey.* (= robust 系集約、 synthesis 改訂後の検討)

---

これで T074 詳細設計は完成。 概念設計 Round 3 APPROVED 状態を起点に、 Round 3 [W1-W4] / [S1-S4] を全反映。 Codex 詳細レビュー (gpt-5.3-codex / high) で最終確認。
