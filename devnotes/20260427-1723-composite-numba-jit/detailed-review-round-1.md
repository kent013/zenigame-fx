**Round 1（C9: Falsification-first）**
まず「この設計で安全に 40-65% 高速化できる」という仮説の反証を先に探しました。主要な反証候補は以下です。  
1. prepared path で既存の例外契約（特に `clauses` 空時 `ValueError`）が崩れる  
2. `on_bar` ボトルネック推定に `cumtime` と `tottime` の混在があり、削減見積りが過大  
3. Python 3.13 + NumPy 2.x + Numba の実運用互換が未確定で、導入自体が失敗しうる  
4. `evaluate_all_bars` 戻り長が揃わない場合、旧実装は bar 単位で 0 補正だが新実装は prepare 時点で破綻しうる  
5. T037（`!= 0.0`）はゼロ近傍で allclose 合格でも破綻しうる  

**前提（C4）**
- `verified`
  - profile 上、`run_backtest` は 16 回・`on_bar` は 229,616 回で、提示値同士は整合
  - Stage B/C が profile で未観測（pass 0/16）は事実
  - 現行 pure Python 契約（`compute_composite` の `ValueError`、`compute_gate` は weight 非使用）は明示されている
- `unverified`
  - 最新 main 実コードとの完全一致（今回は埋め込みテキストのみ）
  - Numba の Python 3.13 実動互換
  - `evaluate_all_bars` が常に `len(bars)` を返す不変条件
  - `--max-workers 6` での cache 競合/再コンパイル挙動
  - Stage B 実際の有効バー数（config 上は 18 months だが dataset は約 6 months）

**指摘（Fact / Interpretation 分離）**

[Critical] 既存例外契約の回帰リスク（prepared path）  
- Fact: 現行は `compute_composite()` が `clauses` 空で `ValueError`。提案 kernel は `n_clauses=0` で `0.0` を返しうる。  
- Interpretation: invalid genome を silent に通し、prepared/unprepared で挙動差が出る。  
- 修正案: `DslStrategy.__init__` か `prepare()` で `clauses` 非空を明示検証し、現行と同じ `ValueError` を強制。回帰テストを追加。

[Critical] Numba 依存の導入可否が未確定（Python 3.13）  
- Fact: 設計書内でも「要 verify」。依存は hard 追加予定。  
- Interpretation: 環境によっては `uv sync` で詰まり、実装が成立しない。  
- 修正案: マージ前に Python 3.11/3.12/3.13 互換マトリクスを実測。不可なら `requires-python` 制約を明示するか、Numba optional + pure Python fallback を採用。

[Critical] 配列長不一致時のセマンティクス差分  
- Fact: 現行 prepared path は `idx < len(arr)` で signal ごとに 0 補正。提案は `unique_signal_matrix` 前提で一括アクセス。  
- Interpretation: `evaluate_all_bars` が短い配列を返す実装が混入した場合、旧は継続・新は prepare で失敗/挙動変更。  
- 修正案: `prepare()` で全配列 `len == n_bars` を検証して明示 `ValueError`、または 0 padding で旧契約を再現。対応テスト必須。

[Warning] `on_bar` 差分 0.69s の解釈が不正確  
- Fact: 1.165s は `on_bar` の `cumtime`、0.473s は composite 系の `tottime` 合計で同次元比較ではない。  
- Interpretation: 改善率 40-65% の根拠が弱く、期待値ブレが大きい。  
- 修正案: `line_profiler`/`py-spy` で `on_bar` 内訳を再計測し、`old vs new` の同一指標で再見積り。

[Warning] T037 exact parity のテストが不足しやすい  
- Fact: allclose 契約と `!= 0.0` 契約は別。ゼロ近傍/符号付きゼロ/サブノーマルで差が出る。  
- Interpretation: aggregate 合格でも active clause 集計だけ壊れる可能性。  
- 修正案: cancellation を狙った決定的ケース（`+0.0/-0.0/1e-320`）を固定テスト化。

[Warning] メモリ見積りが片側（matrix）中心  
- Fact: `arrays` + `unique_signal_matrix` で同等データを二重保持。  
- Interpretation: 見積りは実効でほぼ 2 倍寄り。n_unique 増加時の 3GB/worker 余裕を圧迫。  
- 修正案: メモリ式を `2 * n_unique * n_bars * 8B + α` で再提示し、n_unique 上限を config/validation で管理。

[Suggestion] Stage B/C は現状 INCONCLUSIVE の扱いで妥当  
- Fact: 未観測。  
- Interpretation: 「同方向期待」までに留めるのは適切。  
- 追加提案: Phase 7 で Stage B/C 通過 run を別プロファイル採取して係数分離。

**施策ごとの判定**

1. 依存追加 (numba): **REQUEST_CHANGES**  
2. kernel 追加: **REQUEST_CHANGES**  
3. PreparedSignals 拡張: **REQUEST_CHANGES**  
4. on_bar prepared path 切替: **REQUEST_CHANGES**  
5. テスト整備: **REQUEST_CHANGES**（上記 Critical/Warning を埋める追加テストが必要）  
6. JIT cache 管理: **INCONCLUSIVE**（方針は妥当だが実測結果待ち）  
7. bars_scale 実測スクリプト: **APPROVE**

**観点別補足**
- ルックアヘッドバイアス: **該当なし（スキップ妥当）**  
- Collider bias / 相関解釈（C3/C7）: **本件は性能設計中心で該当薄**  
- C2（並行経路）: unprepared 維持方針は妥当。ただし prepared/unprepared の同値回帰テストを強化すべき。  
- 波及変更（AGENTS/skills/config/docs）: 今回「なし」は許容だが、Numba 導入後の運用ドキュメント追記は次サイクルで必須。

**全体判定**
**CHANGES_REQUESTED**  
設計の方向性自体は妥当ですが、契約維持（例外・T037）と導入可否（Python 3.13/Numba）、配列長不変条件の明文化が未完です。ここを塞げば実装着手可能です。