"""T008 テスト / 暫定用の dummy primitive registry。

T010 primitives-registry で正式 RegistryEvaluator が整備されたら置き換える。
本モジュールは private prefix (`_`) で公開 import を抑制。

ID は `docs/alpha_factory/primitives.md` の name と完全一致させる
（後続 TODO で実 primitive に置換した際の名称衝突を避ける）。
"""

from __future__ import annotations

from typing import Final

from src.ga.random_gen import PrimitiveRegistry, PrimitiveSpec

DUMMY_REGISTRY: Final[PrimitiveRegistry] = {
    # directional
    "TrendEMA": PrimitiveSpec(
        "TrendEMA", "directional", "generic", {"n": (5, 50)}
    ),
    "RSIRevert": PrimitiveSpec(
        "RSIRevert",
        "directional",
        "generic",
        {"n": (5, 30), "level": (20.0, 80.0)},
    ),
    "DonchianBreak": PrimitiveSpec(
        "DonchianBreak", "directional", "generic", {"n": (10, 60)}
    ),
    "ZScoreRevert": PrimitiveSpec(
        "ZScoreRevert", "directional", "generic", {"n": (5, 40)}
    ),
    # modulator
    "SessionGate": PrimitiveSpec(
        "SessionGate",
        "modulator",
        "generic",
        {"start_h": (0, 23), "end_h": (0, 23)},
    ),
    "ATRRegimeGate": PrimitiveSpec(
        "ATRRegimeGate",
        "modulator",
        "generic",
        {"n": (10, 60), "k": (0.5, 2.0)},
    ),
    "TrendStrengthGate": PrimitiveSpec(
        "TrendStrengthGate", "modulator", "generic", {"n": (5, 30)}
    ),
}
