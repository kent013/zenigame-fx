"""Graduation lane scaffold (T074 cascade port v2 Phase 2 配線、 Phase 1 純ライブラリ).

evaluate_graduation_trigger (= epoch 基準 3 条件判定) + multi-pair aggregation
sketch (= worst_pair / mean、 status="not_implemented") + 6 batch pair frozenset
+ GraduationEpochSummary 3 field を提供する。 runtime 未組込 (= 単体 test のみ)、
Phase 2 で T071 RunObservabilityReport.graduation_trigger field 配線時に runtime
に組込予定 (申し送り)。

責務 (詳細設計 § 0):
    - evaluate_graduation_trigger は archive read-only で 3 条件判定のみ
    - GraduationArchiveSummary は archive snapshot 集計の入力契約 (Phase 2 adapter
      責務、 Round R2 [W3] 同一 transaction)
    - GraduationEpochSummary は 1 epoch 単位の集約 (= observed_run_ids /
      mission_pass_run_ids、 issubset SSOT inclusive)
    - MultiPairAggregationSketch は Phase 4 robust 系追加禁止規範 SSOT
      (= synthesis 改訂前は worst_pair / mean のみ)

collider bias 規範継承 (詳細設計 § 8.4 / 概念設計):
    T074 graduation lane scaffold は **collider bias 判定を行わない**.
    holiday_markets / dst_transition_markets / schedule_status の stratified audit
    は Phase 2 で T071 RunObservabilityReport 経由で出力する責務.
    本 module は observability_flags を参照しない (= grep DoD で確認、 Round 3 [S3]).
    multi-pair 集約は scaffold のみ、 Phase 4 で synthesis 改訂前に robust 系
    Literal 追加禁止 (Round 3 [S4]).

Phase 2 申し送り (詳細設計 § 1.3 / § 9.2):
    - T071 RunObservabilityReport.graduation_trigger field 追加
    - run_ga.py 唯一の SSOT adapter (Round R2 [W3] 同一 snapshot transaction、
      Round 3 [S2] config fail-closed)
    - config キー `graduation.recent_epochs_with_mission_pass_required` missing は
      ValueError raise (= 暗黙 default 不可)

Phase 4 申し送り (詳細設計 § 1.4 / § 9.3):
    - compute_multi_pair_aggregation_sketch を実装版に置換 (= worst_pair / mean
      の数値計算)
    - GraduationLane.run_generation の実装 (= NotImplementedError → 実装)
    - GraduationBatchInput / GraduationBatchReport dataclass 導入 (Phase 1 では
      死蔵 risk 排除)
    - GRADUATION_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 (MINOR bump、 後方互換)
    - robust 系 aggregation (= worst-case CVaR 等) は **synthesis_schema_version
      >= 22 まで MultiPairAggregationKind Literal に追加禁止** (Round 3 [S4] /
      Round D3 [S2] 反映)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

__all__ = [
    "GRADUATION_AGGREGATION_CALC_VERSION",
    "GRADUATION_BATCH_PAIRS",
    "GRADUATION_REPORT_SCHEMA_VERSION",
    "GRADUATION_TRIGGER_CALC_VERSION",
    "GRADUATION_TRIGGER_MIN_EPOCHS",
    "GRADUATION_TRIGGER_MIN_GRADUATES",
    "LANE_PARALLELISM",
    "GraduationArchiveSummary",
    "GraduationEpochSummary",
    "GraduationTriggerEvaluation",
    "GraduationTriggerStatus",
    "MultiPairAggregationKind",
    "MultiPairAggregationSketch",
    "MultiPairAggregationStatus",
    "compute_multi_pair_aggregation_sketch",
    "evaluate_graduation_trigger",
]


# ---------------------------------------------------------------------------
# Literal types (status field 方式、 Round 3 [S4] robust 系追加禁止規範)
# ---------------------------------------------------------------------------

GraduationTriggerStatus = Literal[
    "ready",
    "insufficient_graduates",
    "insufficient_epochs",
    "no_recent_mission_pass",
]
"""evaluate_graduation_trigger の status field 4 値 (disjoint 優先順)."""

MultiPairAggregationKind = Literal["worst_pair", "mean"]
"""multi-pair 集約 2 種 (synthesis § 11.2 確定値).

Phase 4 robust 系追加禁止規範 (Round 3 [S4] / Round D3 [S2]):
    synthesis_schema_version >= 22 まで Literal に追加禁止.
    synthesis Round 22 改訂 PR で `synthesis_schema_version: 22` を明示追加した
    後でなければ worst-case CVaR 等の robust 系 kind を追加してはならない.
"""

MultiPairAggregationStatus = Literal["not_implemented"]
"""scaffold 段階の status 1 値 (= status field 方式、 数値 field なし)."""


# ---------------------------------------------------------------------------
# 定数 (synthesis § 11.1 / § 5.4 / Round R2 [S4])
# ---------------------------------------------------------------------------

GRADUATION_TRIGGER_MIN_GRADUATES: Final[int] = 24
"""synthesis § 11.1: graduation trigger の最小 graduate 数 (= 24)."""

GRADUATION_TRIGGER_MIN_EPOCHS: Final[int] = 3
"""synthesis § 11.1: graduation trigger の最小 distinct epoch 数 (= 3)."""

GRADUATION_BATCH_PAIRS: Final[frozenset[str]] = frozenset(
    {
        "EUR_JPY",
        "USD_JPY",
        "EUR_USD",
        "AUD_JPY",
        "USD_CAD",
        "USD_ZAR",
    }
)
"""synthesis § 5.4: graduation batch 6 pair (= STAGE_C_ANCHOR_PAIR ∪
STAGE_C_SHADOW_PAIR_LIST 集合等価、 順序非依存).

Round R2 [S4] 反映: production module は STAGE_C_ANCHOR_PAIR /
STAGE_C_SHADOW_PAIR_LIST を import せず、 集合等価性は test 側で確認 (=
F26_t064_set_equal). 既存 stage_bc_evaluator.py 非侵襲.
"""

LANE_PARALLELISM: Final[int] = 1
"""synthesis: Phase 1/2 lane 並列度 (= 1 で逐次実行、 Phase 4 で再評価).

Phase 4 で multi-pair 集約計算実装時、 lane 並列実行は別途設計判断.
"""

GRADUATION_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
"""GraduationReport の schema version (Phase 4 で 1.1.0 に MINOR bump 予定)."""

GRADUATION_TRIGGER_CALC_VERSION: Final[str] = "v1"
"""evaluate_graduation_trigger の calc_version (= 3 条件判定実装の identity)."""

GRADUATION_AGGREGATION_CALC_VERSION: Final[str] = "scaffold-v1"
"""multi-pair aggregation の calc_version (= scaffold 段階).

Phase 4 で worst_pair / mean 数値計算を実装した時点で別 version (=
"v1" or 同等) に置換、 schema_version も MINOR bump.
"""


# ---------------------------------------------------------------------------
# GraduationEpochSummary (1 epoch 単位の集約)
# ---------------------------------------------------------------------------


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
                "GraduationEpochSummary.dataset_epoch_id must be non-empty"
            )
        if not self.observed_run_ids:
            raise ValueError(
                "GraduationEpochSummary.observed_run_ids must be non-empty "
                f"(epoch_id={self.dataset_epoch_id!r})"
            )
        # Round 3 [W1]: issubset (inclusive) で SSOT
        if not self.mission_pass_run_ids.issubset(self.observed_run_ids):
            extra = self.mission_pass_run_ids - self.observed_run_ids
            raise ValueError(
                "GraduationEpochSummary.mission_pass_run_ids must be subset of "
                f"observed_run_ids (epoch_id={self.dataset_epoch_id!r}): "
                f"extra={sorted(extra)}"
            )

    @property
    def has_mission_pass(self) -> bool:
        """Round R2 [C1]: mission pass run の有無で導出."""
        return bool(self.mission_pass_run_ids)


# ---------------------------------------------------------------------------
# GraduationArchiveSummary (archive snapshot 集計の入力契約)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraduationArchiveSummary:
    """archive read-only の評価時点 snapshot 集計 (caller responsibility).

    SSOT:
        n_graduates: 評価時点 snapshot の graduated=True 数 (Round R1 [W6])
        distinct_dataset_epoch_ids: 評価時点 snapshot の distinct epoch 集合 (空集合許容)
        recent_epoch_summaries: 直近 N+ epoch の GraduationEpochSummary 列
            **新しい順、 [0] が active/current、 以降古い epoch へ進む** (Round 3 [S1])
            epoch 単位 unique
        archive_epoch_id_active: str | None (Round R2 [C2])
            None = empty archive (= distinct 空 + recent 空)
            non-None = active epoch あり (= [0]==active 一致 invariant)

    Phase 2 adapter contract (Round 3 [W2] [W4] / Round D1 [W8]):
        - 同一 archive snapshot から単一 transaction で構築 (Round R2 [W3])
        - 「active epoch はあるが recent_epoch_summaries 未構築」 中間状態は本
          contract 範囲外 (= 別 TODO で contract 拡張)
        - recent_epoch_summaries[1:] の順序正当性 (= 古い順) は __post_init__ で
          検出不能、 Phase 2 adapter test 責務

    raise 順序 仕様 (Round D1 [W2] 反映): I-1 → I-2 → I-3 → I-4
        各 invariant は前段の検証通過を前提とし、 順序依存で raise message が一意.
    """

    n_graduates: int
    distinct_dataset_epoch_ids: frozenset[str]
    recent_epoch_summaries: tuple[GraduationEpochSummary, ...]
    archive_epoch_id_active: str | None

    def __post_init__(self) -> None:
        # I-1: n_graduates >= 0
        if self.n_graduates < 0:
            raise ValueError(
                f"n_graduates >= 0 required, got {self.n_graduates}"
            )

        # I-2: recent_epoch_summaries の epoch 単位ユニーク性
        seen_epoch_ids: set[str] = set()
        for s in self.recent_epoch_summaries:
            if s.dataset_epoch_id in seen_epoch_ids:
                raise ValueError(
                    "recent_epoch_summaries duplicate dataset_epoch_id: "
                    f"{s.dataset_epoch_id!r}"
                )
            seen_epoch_ids.add(s.dataset_epoch_id)

        # I-3: 全 recent[i].dataset_epoch_id ∈ distinct_dataset_epoch_ids
        for s in self.recent_epoch_summaries:
            if s.dataset_epoch_id not in self.distinct_dataset_epoch_ids:
                raise ValueError(
                    f"recent_epoch_summaries[{s.dataset_epoch_id!r}] not in "
                    "distinct_dataset_epoch_ids "
                    f"({sorted(self.distinct_dataset_epoch_ids)})"
                )

        # I-4: archive_epoch_id_active 整合 (Round R2 [C2] / Round 3 [W4])
        if self.archive_epoch_id_active is None:
            # empty archive case
            if self.distinct_dataset_epoch_ids:
                raise ValueError(
                    "archive_epoch_id_active=None requires empty "
                    "distinct_dataset_epoch_ids, got "
                    f"{sorted(self.distinct_dataset_epoch_ids)}"
                )
            if self.recent_epoch_summaries:
                raise ValueError(
                    "archive_epoch_id_active=None requires empty "
                    "recent_epoch_summaries, got len="
                    f"{len(self.recent_epoch_summaries)}"
                )
        else:
            # non-None case
            if self.archive_epoch_id_active not in self.distinct_dataset_epoch_ids:
                raise ValueError(
                    "archive_epoch_id_active="
                    f"{self.archive_epoch_id_active!r} not in "
                    "distinct_dataset_epoch_ids"
                )
            if self.recent_epoch_summaries:
                head = self.recent_epoch_summaries[0]
                if head.dataset_epoch_id != self.archive_epoch_id_active:
                    raise ValueError(
                        "recent_epoch_summaries[0].dataset_epoch_id "
                        f"({head.dataset_epoch_id!r}) != "
                        "archive_epoch_id_active "
                        f"({self.archive_epoch_id_active!r})"
                    )
        # 注: recent_epoch_summaries[1:] の順序正当性 (= 古い順) は __post_init__
        #     で検出不能. Phase 2 adapter test の責務 (Round 3 [W2]).


# ---------------------------------------------------------------------------
# GraduationTriggerEvaluation (3 条件判定結果)
# ---------------------------------------------------------------------------


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
        3. 直近 N epoch すべてで has_mission_pass 不充足        → "no_recent_mission_pass"
        4. 全達成                                                → "ready"

    raise 順序 仕様 (Round D1 [W2] [C1] / Round D3 [W1] 反映):
        I-1 calc_version → I-2 実測値範囲 → I-2b cross-field invariant →
        I-3 status 別 invariant
    """

    status: GraduationTriggerStatus
    n_graduates: int
    n_distinct_epochs: int
    recent_mission_pass_epoch_ids: tuple[str, ...]
    has_recent_mission_pass: bool
    recent_epochs_required: int
    calc_version: str

    def __post_init__(self) -> None:
        # I-1: calc_version
        if self.calc_version != GRADUATION_TRIGGER_CALC_VERSION:
            raise ValueError(
                f"calc_version must be {GRADUATION_TRIGGER_CALC_VERSION!r}, "
                f"got {self.calc_version!r}"
            )

        # I-2: 実測値範囲
        if self.n_graduates < 0:
            raise ValueError(
                f"n_graduates >= 0 required, got {self.n_graduates}"
            )
        if self.n_distinct_epochs < 0:
            raise ValueError(
                f"n_distinct_epochs >= 0 required, got {self.n_distinct_epochs}"
            )
        # Round D1 [C1]: dataclass 直接構築でも recent_epochs_required >= 1 を invariant 化
        if self.recent_epochs_required < 1:
            raise ValueError(
                "recent_epochs_required >= 1 required, got "
                f"{self.recent_epochs_required}"
            )

        # I-2b: cross-field invariant (Round D3 [W1] 反映)
        # duplicate 禁止
        if len(set(self.recent_mission_pass_epoch_ids)) != len(
            self.recent_mission_pass_epoch_ids
        ):
            raise ValueError(
                "recent_mission_pass_epoch_ids must be unique, got duplicates "
                f"in {self.recent_mission_pass_epoch_ids}"
            )
        # mission pass epoch は distinct epoch の subset
        # (= n_distinct_epochs >= len(unique mission pass))
        if self.n_distinct_epochs < len(self.recent_mission_pass_epoch_ids):
            raise ValueError(
                f"n_distinct_epochs ({self.n_distinct_epochs}) >= "
                "len(recent_mission_pass_epoch_ids) "
                f"({len(self.recent_mission_pass_epoch_ids)}) required "
                "(mission pass epochs subset of distinct epochs)"
            )

        # I-3: status 別 invariant (Round 3 [W3] / Round D1 [W3] / Round D2 [W1] 反映)
        n_recent = len(self.recent_mission_pass_epoch_ids)
        if self.status == "ready":
            if self.n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    "status='ready' requires n_graduates >= "
                    f"{GRADUATION_TRIGGER_MIN_GRADUATES}, got {self.n_graduates}"
                )
            if self.n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS:
                raise ValueError(
                    "status='ready' requires n_distinct_epochs >= "
                    f"{GRADUATION_TRIGGER_MIN_EPOCHS}, got {self.n_distinct_epochs}"
                )
            if n_recent != self.recent_epochs_required:
                raise ValueError(
                    "status='ready' requires len(recent_mission_pass_epoch_ids)"
                    f" == recent_epochs_required ({self.recent_epochs_required}),"
                    f" got {n_recent}"
                )
            if not self.has_recent_mission_pass:
                raise ValueError(
                    "status='ready' requires has_recent_mission_pass == True"
                )
        elif self.status == "insufficient_graduates":
            if self.n_graduates >= GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    "status='insufficient_graduates' requires n_graduates < "
                    f"{GRADUATION_TRIGGER_MIN_GRADUATES}, got {self.n_graduates}"
                )
            if n_recent != 0:
                raise ValueError(
                    "status='insufficient_graduates' requires "
                    "recent_mission_pass_epoch_ids empty (early return), "
                    f"got len={n_recent}"
                )
            if self.has_recent_mission_pass:
                raise ValueError(
                    "status='insufficient_graduates' requires "
                    "has_recent_mission_pass == False"
                )
        elif self.status == "insufficient_epochs":
            if self.n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    "status='insufficient_epochs' implies graduates condition "
                    f"OK, got n_graduates={self.n_graduates}"
                )
            if self.n_distinct_epochs >= GRADUATION_TRIGGER_MIN_EPOCHS:
                raise ValueError(
                    "status='insufficient_epochs' requires n_distinct_epochs "
                    f"< {GRADUATION_TRIGGER_MIN_EPOCHS}, got "
                    f"{self.n_distinct_epochs}"
                )
            if n_recent != 0:
                raise ValueError(
                    "status='insufficient_epochs' requires "
                    f"recent_mission_pass_epoch_ids empty, got len={n_recent}"
                )
            if self.has_recent_mission_pass:
                raise ValueError(
                    "status='insufficient_epochs' requires "
                    "has_recent_mission_pass == False"
                )
        elif self.status == "no_recent_mission_pass":
            # Round D2 [W1]: partial pass diagnostic 許容
            #   recent_mission_pass_epoch_ids は **実測値**
            #   (= 直近 N epoch のうち実際に pass した ids)
            #   "no_recent_mission_pass" は「N 個中 N 未満」 を表現
            #   (= 0..N-1 個 pass)
            #   早期 return (= recent_epoch_summaries が required 未満) も含む
            if self.n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
                raise ValueError(
                    "status='no_recent_mission_pass' implies graduates "
                    f"condition OK, got n_graduates={self.n_graduates}"
                )
            if self.n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS:
                raise ValueError(
                    "status='no_recent_mission_pass' implies epochs condition "
                    f"OK, got n_distinct_epochs={self.n_distinct_epochs}"
                )
            # Round D2 [W1]: 0 <= len < required (= partial pass 許容)
            if not (0 <= n_recent < self.recent_epochs_required):
                raise ValueError(
                    "status='no_recent_mission_pass' requires "
                    "0 <= len(recent_mission_pass_epoch_ids) < "
                    f"recent_epochs_required ({self.recent_epochs_required}), "
                    f"got len={n_recent}"
                )
            if self.has_recent_mission_pass:
                raise ValueError(
                    "status='no_recent_mission_pass' requires "
                    "has_recent_mission_pass == False"
                )
        else:
            raise ValueError(
                f"unknown GraduationTriggerStatus: {self.status!r}"
            )


# ---------------------------------------------------------------------------
# MultiPairAggregationSketch (T073 SSOT 継承、 Phase 4 で実装)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiPairAggregationSketch:
    """multi-pair 集約 scaffold (Phase 4 で実装).

    Phase 4 robust 系追加禁止規範 (Round 3 [S4]):
        synthesis § 11.2 確定値 = worst_pair / mean のみ.
        robust 系 (= worst-case CVaR 等) は **synthesis 改訂前に
        MultiPairAggregationKind Literal に追加禁止**.
        Phase 4 で実装する場合は synthesis Round 22 改訂で worst_pair / mean 以外
        を確定後、 Literal 拡張.
    """

    kind: MultiPairAggregationKind
    status: MultiPairAggregationStatus
    calc_version: str

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(
                "MultiPairAggregationSketch.status must be 'not_implemented', "
                f"got {self.status!r}"
            )
        if self.calc_version != GRADUATION_AGGREGATION_CALC_VERSION:
            raise ValueError(
                f"calc_version must be {GRADUATION_AGGREGATION_CALC_VERSION!r}"
                f", got {self.calc_version!r}"
            )


# ---------------------------------------------------------------------------
# evaluate_graduation_trigger (3 条件判定 disjoint)
# ---------------------------------------------------------------------------


def _make_trigger(
    *,
    status: GraduationTriggerStatus,
    n_graduates: int,
    n_distinct_epochs: int,
    recent_mission_pass_epoch_ids: tuple[str, ...],
    recent_epochs_required: int,
) -> GraduationTriggerEvaluation:
    """Round 3 [W3] / Round D1 [S1] keyword-only.

    has_recent_mission_pass は status 従属 (= status="ready" のみ True、
    実データ独立評価ではない).
    """
    has_pass = status == "ready"
    return GraduationTriggerEvaluation(
        status=status,
        n_graduates=n_graduates,
        n_distinct_epochs=n_distinct_epochs,
        recent_mission_pass_epoch_ids=recent_mission_pass_epoch_ids,
        has_recent_mission_pass=has_pass,
        recent_epochs_required=recent_epochs_required,
        calc_version=GRADUATION_TRIGGER_CALC_VERSION,
    )


def evaluate_graduation_trigger(
    *,
    archive_summary: GraduationArchiveSummary,
    recent_epochs_with_mission_pass_required: int,
) -> GraduationTriggerEvaluation:
    """archive read-only で 3 条件判定 (synthesis § 11.1).

    Phase 2 adapter responsibility (Round 3 [S2]):
        config キー `graduation.recent_epochs_with_mission_pass_required` から
        caller が値を渡す. config missing 時は caller が ValueError raise
        (= 暗黙 default 不可、 fail-closed).

    優先順位 (disjoint):
        1. n_graduates < 24                                 → "insufficient_graduates"
        2. distinct epoch < 3                               → "insufficient_epochs"
        3. 直近 N epoch すべてで has_mission_pass 不充足    → "no_recent_mission_pass"
        4. 全達成                                            → "ready"

    Args:
        archive_summary: archive snapshot 集計入力. caller (Phase 2 で run_ga.py)
            が同一 transaction 内で構築する責務.
        recent_epochs_with_mission_pass_required: caller 引数.
            config `graduation.recent_epochs_with_mission_pass_required` から
            渡される. >= 1 必須.

    Returns:
        GraduationTriggerEvaluation: status field 方式の判定結果.

    Raises:
        ValueError: recent_epochs_with_mission_pass_required < 1.
    """
    if recent_epochs_with_mission_pass_required < 1:
        raise ValueError(
            "recent_epochs_with_mission_pass_required >= 1 required, "
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
        # Round D2 [W1]: partial pass diagnostic を保持
        # (= 実測値で「N 中何個 pass か」 を caller に提示)
        return _make_trigger(
            status="no_recent_mission_pass",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=mission_pass_epoch_ids,
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


# ---------------------------------------------------------------------------
# compute_multi_pair_aggregation_sketch (Phase 4 で実装版に置換)
# ---------------------------------------------------------------------------


def compute_multi_pair_aggregation_sketch(
    *,
    kind: MultiPairAggregationKind,
    calc_version: str = GRADUATION_AGGREGATION_CALC_VERSION,
) -> MultiPairAggregationSketch:
    """multi-pair 集約 scaffold factory (Phase 4 で実装版に置換).

    Phase 4 で worst_pair / mean の数値計算を実装するまで status="not_implemented"
    固定. NotImplementedError は raise しない (= scaffold は存在自体が SSOT).

    Args:
        kind: "worst_pair" | "mean" (synthesis § 11.2 確定 2 値).
            Round 3 [S4]: synthesis 改訂前に robust 系追加禁止.
        calc_version: GRADUATION_AGGREGATION_CALC_VERSION (= "scaffold-v1") のみ
            許容. 異なる場合 MultiPairAggregationSketch.__post_init__ で raise.

    Returns:
        MultiPairAggregationSketch: status="not_implemented" / calc_version=
        "scaffold-v1".
    """
    return MultiPairAggregationSketch(
        kind=kind,
        status="not_implemented",
        calc_version=calc_version,
    )
