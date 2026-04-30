**Round 2 再レビュー（C9: 反証先行）**

まず反証観点で確認しました。  
「Round 1 の Critical 3件が設計上で未解消ではないか」を先に見ましたが、提示内容ベースでは **3件とも設計要件としては解消**されています。

**前提（C4）**
- `verified`
  - `clauses` 空の契約維持を `prepare()` fail-fast + V10 + テスト追加で明文化
  - 配列長不一致を `prepare()` fail-fast + V11 + テスト追加で明文化
  - T037 ゼロ近傍ケースを V13 と決定的テストで明文化
  - `on_bar` 内訳再計測を V14 として要件化
  - メモリ式を `2 × n_unique × n_bars × 8B + α` に更新
- `unverified`
  - Numba × Python 3.13 互換性そのもの（V12 実行前）
  - 施策 1/2 の本文（今回抜粋が空のため、記述完全性は未確認）

**Round 1 指摘の解消判定（Fact / Interpretation）**

1. [Critical 1] clauses 空時の ValueError 契約  
- Fact: `prepare()` に `if not self._genome.clauses: raise ValueError(...)` を追加し、V10 とテストを追加。  
- Interpretation: **解消**（契約回帰リスクは設計上クローズ）。

2. [Critical 2] Numba × Python 3.13 互換性  
- Fact: V12 と中断条件・fallback 方針を明記。  
- Interpretation: **設計として解消**（実行時検証ゲート化できている）。

3. [Critical 3] 配列長不一致 semantics  
- Fact: `arr.shape != (n_bars,)` で fail-fast + V11 + 4/6 長テスト。  
- Interpretation: **解消**（暗黙 0 補正との差分を意図的に禁止し、契約を明確化）。

4. [Warning 1] 0.69s 解釈  
- Fact: V14 で同一指標再計測を要求。  
- Interpretation: **解消**。

5. [Warning 2] T037 ゼロ近傍  
- Fact: `signed zero/subnormal/cancellation` の決定的ケースを追加。  
- Interpretation: **解消**。

6. [Warning 3] メモリ見積り片側  
- Fact: 二重保持前提に修正し、worker 合計試算まで追加。  
- Interpretation: **解消**。

7. [Suggestion] Stage B/C INCONCLUSIVE 維持  
- Fact: 既に反映済み。  
- Interpretation: **解消**。

**新規指摘**

[Warning] `arr.shape` 前提が `np.ndarray` 固定寄り  
- Fact: `arr = evaluate_all_bars(...)` の直後に `arr.shape` を参照しており、返り値が list/Series の場合に `AttributeError` 化する余地がある。  
- Interpretation: 現 evaluator が ndarray なら問題化しないが、将来実装の拡張性を狭める。  
- 修正案: `arr = np.asarray(..., dtype=np.float64)` の後に shape 検証し、例外を `ValueError` に統一。

**各施策の判定**

1. 依存追加 (numba): **APPROVE**  
2. kernel 追加: **APPROVE**  
3. PreparedSignals 拡張: **APPROVE**（上記 Warning の軽微追補推奨）  
4. on_bar prepared path 切替: **APPROVE**  
5. テスト整備: **APPROVE**  
6. JIT cache 管理: **INCONCLUSIVE**（実測依存のため判定留保）  
7. bars_scale_a 実測スクリプト: **APPROVE**

**観点補足**
- ルックアヘッドバイアス: 該当なし（primitive 変更なし）  
- Collider bias / n<30 相関解釈: 該当なし（本件は性能設計レビュー）  
- C2 並行経路: unprepared 経路維持方針は妥当

**全体判定**
**APPROVED**（実装着手可）  
※ ただし V12（互換性ゲート）と V14（性能内訳再計測）はマージ判断の必須ゲートとして運用してください。