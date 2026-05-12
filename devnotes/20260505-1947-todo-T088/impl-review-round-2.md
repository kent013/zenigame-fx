**前提**
- 仮説: Round 1 の唯一の数値不変性リスクは `seed=±inf` を early return に巻き込む点であり、`np.isnan(seed)` 限定に戻せば現行 semantics と一致する。
- 成功条件: `seed=NaN` は全 NaN 維持、`seed=±inf` は `out[n-1]=±inf` から recurrence に流れ、rolling min/max は deque 版と同じ単調キュー契約を満たす。

**ファイル別判定**
- `src/alpha_factory/primitives/_indicators.py`: `APPROVED`
- `tests/alpha_factory/primitives/test_indicators.py`: `APPROVED`

**Findings**
- [Critical] なし。
- [Warning] なし。
- [Suggestion] `v == v` コメントは意図説明として適切です。ただし「Numba 互換性が高い」はやや一般化が強いので、将来の保守性だけを見るなら「float64 前提で NaN 判定を分岐コスト少なく行う」程度でも十分です。非ブロッカーです。

**確認結果**
- `np.isnan(seed)` 限定 early return は設計どおりです。`seed=±inf` は early return せず、旧実装同様に `out[n-1]=±inf` を設定して recurrence に流れるため、有限後続値に対しても `±inf` が伝播します。
- `seed=NaN` の early return も旧実装と値として一致します。旧実装は `prev=NaN` から以降も NaN 伝播、新実装は `out` 初期値の全 NaN を返すため、出力配列の値契約は同一です。
- `v == v` は `float64` 前提では `np.isnan(v)` の否定と等価です。`±inf` は true、`NaN` のみ false なので recurrence 契約に合っています。
- `rolling_min` の head/tail/size 管理は提示コード上 `rolling_max` と対称で、`n=1` でも drop → insert → output の順序が成立します。comparator `>=` による右側 drop も min deque の重複値処理として設計と一致します。
- inf seed parity test の追加により、Round 1 の `np.isfinite` 回帰は検出可能になっています。

**全体判定**
- `APPROVED`

提供された Round 2 差分・テスト結果を前提に、T088 の設計反映、数値不変契約、Numba 化方針、テスト網羅はいずれも承認可能です。