# Round 2 Detailed Design Review

## 施策 1, 2 (Round 1 APPROVE 維持) 評価
- 判定: **維持で問題なし**。Round 2 で変更が入っていない前提なら、Round 1 の APPROVE をそのまま据え置いてよいです。

## 施策 3 (Round 2 refactor) 判定
**APPROVE** - 理由  
- seed を Python 側で `np.nanmean` 系の計算に戻したことで、Round 1 Critical（manual seed による丸め順序差）を解消できています。  
- JIT 化対象を recurrence のみに限定しているため、parity 上のリスク面が明確に分離されています。  
- `out` への in-place 書き込みは Numba 的に通常の安全な使い方です（呼び出し側で `out` を新規確保しており、`values` と alias しない設計のため）。

## parity test 拡張 評価
- 判定: **十分**。  
- self-contained oracle 化は Warning 指摘に適合しています。  
- `n=1`、重複値連続、NaN 系、`length < n` を含めたのは妥当です。  
- 実装上は `allclose` ではなく、NaN マスク一致 + 有限値の厳密一致（`assert_array_equal`）で固定すると「exact parity」要件により強く一致します。

## 全体判定
**APPROVED**

## 主要指摘 / 推奨事項
- Blocker はありません。  
- 非 blocker の改善提案のみ:
1. 変数名 `inv_n_m1` / `inv_n` は「inverse」ではないので、`n_minus_1` / `n_float` などへ改名すると可読性が上がります。  
2. parity test は「NaN 位置一致」と「有限値厳密一致」を分離して明示すると、意図がさらに明確になります。