"""T058: RunContext — 1 Run 全体で固定される runtime context.

``run_ga.py`` の startup で生成、 全 component (GA loop, archive, calibrate,
diagnostics, FSP, sieve) が同じ source から ``dataset_epoch_id`` 等を読む。

T058 段階の必須注入は archive / calibrate / diagnostics の主要 3 component
のみ。 全 component 必須化は T059 / T063 合流時に段階的に締める。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.alpha_factory.schema_contract import validate_epoch_id

if TYPE_CHECKING:
    from src.alpha_factory.config import DatasetConfig

__all__ = ["RunContext", "generate_epoch_id_stub"]


@dataclass(frozen=True)
class RunContext:
    """1 Run スコープの runtime context.

    Attributes:
        run_id: ``run_YYYYMMDD_HHMMSS`` 形式の Run 識別子。
        run_number: Run の連番 (e.g., 26)。
        dataset_epoch_id: epoch-rolling 識別子 (T059 で生成)。
        base_config_hash: config hash (calibrate-gate scope 用)。
        instrument: anchor pair (e.g., ``EUR_JPY``)。
    """

    run_id: str
    run_number: int
    dataset_epoch_id: str
    base_config_hash: str
    instrument: str

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_context.run_id must be non-empty")
        if self.run_number < 0:
            raise ValueError(
                f"run_context.run_number must be >= 0: {self.run_number}"
            )
        # grammar 検証は schema_contract.validate_epoch_id 経由
        validate_epoch_id(self.dataset_epoch_id)
        if not self.base_config_hash:
            raise ValueError("run_context.base_config_hash must be non-empty")
        if not self.instrument:
            raise ValueError("run_context.instrument must be non-empty")


# ---------------------------------------------------------------------------
# T058 stub: T059 で deterministic 生成に置換
# ---------------------------------------------------------------------------


def generate_epoch_id_stub(dataset_cfg: DatasetConfig) -> str:
    """T058 stub: dataset_epoch_id の固定 stub 値を返す.

    T058 段階では deterministic 生成 (T059 で実装) が未着手のため、
    全経路で同一の ``"epoch_legacy"`` を返す。 grammar [a-z0-9_]+ 適合済。

    T059 完了後、 dataset の (instrument / start / end / data hash 等) から
    deterministic な epoch-rolling 識別子を生成する関数に置換される。

    Args:
        dataset_cfg: 現段階では参照しないが、 T059 移行時の signature 互換のため
            受け取る (実装側が引数欠落で壊れない)。
    """
    del dataset_cfg  # T058 段階では未使用 (T059 で hash 計算に使う)
    return "epoch_legacy"
