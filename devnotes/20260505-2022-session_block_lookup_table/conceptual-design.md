# 概念設計: `compute_bucket_for_bar` の hour-indexed O(1) lookup table 化

## 背景・課題

profile-optimize cycle 2/3 で profile RUN (`profile_20260505_201359`、 cycle 1/3 後 baseline) を計測した結果:

| 関数 | profile tottime | 呼び出し回数 | per-call | 本番投影 (×295.9) |
|---|---|---|---|---|
| `compute_bucket_for_bar` (line 304) | 0.703s | 1,777,180 | **0.40 μs** | 208s = 3.5 分 |

実 RUN baseline 102 分 (cycle 1/3 後 94 分) に対して **3.5 分 = 3.5%** の hot path。 lookup table 化で per-call 0.05 μs まで削減できれば **~3% 削減見込み**。

## 改善アイデア

現実装は `BLOCK_BUCKET_RANGES_UTC.items()` を 24 時間ループでスキャンして bucket を判定。 これを **24 要素の hour-indexed tuple** で O(1) lookup に置換。

### 現実装 (line 322-329)
```python
hour = bar_time.hour
for bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
    if start <= hour < end:
        return bucket
raise RuntimeError(...)
```

### 改善実装
```python
# import レベルで一度だけ構築
_HOUR_TO_BUCKET: Final[tuple[SessionBlockBucket, ...]] = _build_hour_to_bucket()

def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    # tzinfo / UTC offset validation 維持
    ...
    return _HOUR_TO_BUCKET[bar_time.hour]
```

`_build_hour_to_bucket()` は import 時に `BLOCK_BUCKET_RANGES_UTC` から 24 要素 tuple を構築し、 24h covering の partition violation を **startup 時に検出** (現実装の per-call RuntimeError と同等の防御)。

## 期待効果 (Round 1 修正版: 保守化)

Codex Round 1 指摘: 現行は 3 要素走査 (24h ループではなく)、 主因は `utcoffset()` validation + Python call overhead。 lookup table だけでは劇的削減は未立証。 **microbenchmark で確認** が DoD に必須。

- per-call 0.40 μs → **~0.10-0.20 μs** (microbenchmark で要確認、 first hypothesis)
- profile tottime 0.703s → 0.2-0.4s (40-70% 削減見込み)
- **本番 RUN 削減 first hypothesis**: 1.5-3% (-1.5〜3 分、 target 3% は **upside**)
- 副次効果: covering violation を startup 時に検出 (= **startup invariant への変更**、 後述)

## 実装方針 (概要)

### 変更コンポーネント

1. **`src/backtest/session_block.py`**:
   - `_HOUR_TO_BUCKET` constant 追加 (import レベル、 `Final[tuple[SessionBlockBucket, ...]]`)
   - `_build_hour_to_bucket()` private function (startup 時 partition validation)
   - `compute_bucket_for_bar` 関数本体を `_HOUR_TO_BUCKET[bar_time.hour]` 参照に置換 (validation 部分は維持)

### 数値同値性保証

- 同じ hour → 同じ bucket (BLOCK_BUCKET_RANGES_UTC SSOT 不変)
- tzinfo / UTC offset validation の挙動完全維持
- 既存 test (`tests/backtest/test_session_block.py:446` 等) 全 pass

### startup invariant への変更 (Round 1 Warning 対応)

partition violation エラーの送出タイミングが **per-call → import 時** に変わる。 これは厳密には契約変更:

- BEFORE: 各 `compute_bucket_for_bar` 呼び出しで partition violation が detect される
- AFTER: module import 時に `_build_hour_to_bucket()` が partition violation を detect (= startup invariant)

→ 既存 docstring + 概念設計で **「startup invariant」 として明記**。 互換性厳密維持が必要なら関数側の defensive path も残す選択肢あり (詳細設計で判断)。

### `_build_hour_to_bucket()` 検証対象 (Round 1 Suggestion 対応)

builder は SSOT 派生 + 以下の **構造検証** を行う:

1. 各 (start, end) で `0 <= start < end <= 24`
2. bucket 同士の重複なし (range 排他性)
3. 24 要素 (hours 0-23) 全てが少なくとも 1 bucket に属する (covering)
4. (上記から派生) total length sum = 24

これにより partition contract violation を early-fail。

### Numba 不要

純 Python tuple index lookup で十分。 Numba JIT のメンテナンスコスト追加なし。

## 制約・前提

- **FX 絶対制約**: bucket 計算は session 帰属判定のみ、 取引執行・PnL 計算に影響なし
- **メモリ制約**: 24 要素 tuple = ~200 bytes、 メモリ影響なし
- **既存契約**: `BLOCK_BUCKET_RANGES_UTC` (tokyo: [0,8), london: [8,16), ny: [16,24)) を SSOT として維持、 lookup table はそこから派生
- **依存性**: 本関数は `compute_bucket_for_trade` (line 332) からも呼ばれ、 `aggregate_session_blocks` (line 337) で間接利用
- **import 副作用**: `_HOUR_TO_BUCKET` 構築時に `BLOCK_BUCKET_RANGES_UTC` の 24h covering 検証 → import 時 RuntimeError 化、 これは partition contract violation の早期検出として **改善**

## スコープ外

- broker mock 系 Decimal 改善 (型変更で大規模、 cycle スコープ外)
- DSL composite kernel 拡張 (前 cycle で reject 済)
- per-bar logging 削減 (cycle 3/3 候補)
- `aggregate_session_blocks` 等 session_block.py の他関数 (現 profile では hot path 外)

## 参考

- profile data: `.cache/alpha_factory/runs/profile/profile_20260505_201359.txt` (cycle 1/3 後 baseline)
- 既存実装: `src/backtest/session_block.py:304-329`
- 既存 SSOT: `BLOCK_BUCKET_RANGES_UTC` (line 75-79)
- cycle 1/3 で確立した最小変更パターン: T088 詳細設計 (`devnotes/20260505-1857-indicators_numba_jit/detailed-design.md`)
