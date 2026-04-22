# Concept: primitives-registry

## 目的

全 primitive（32 個）を一元管理する registry を実装。GA の random_gen / serialize / analyze がこれを参照。

## 設計

`src/alpha_factory/primitives/_registry.py`:

```python
from dataclasses import dataclass
from typing import Callable
import numpy as np

@dataclass(frozen=True)
class PrimitiveSpec:
    id: str
    name: str
    category: Literal["TREND_FOLLOW", "MEAN_REVERT", "NEUTRAL", "MODULATOR"]
    compute: Callable[..., float]
    compute_all_bars: Callable[..., np.ndarray]
    param_schema: dict  # {"fast_n": (min, max, default), ...}
    required_data: list[str]  # ["ohlc", "atr", "vix_daily"] etc.

PRIMITIVE_REGISTRY: dict[str, PrimitiveSpec] = {
    "F1": PrimitiveSpec(id="F1", name="TrendEMA", ...),
    ...
}

def get_primitive(id: str) -> PrimitiveSpec: ...
def list_by_category(category) -> list[PrimitiveSpec]: ...
```

## テスト

- 全 primitive が登録されている
- `list_by_category("TREND_FOLLOW")` で期待する IDs
- param_schema のレンジが全 primitive で定義されている

## 優先度・モード

- Priority: High
- Mode: incremental
- テーマ: primitives
