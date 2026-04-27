**前提（C4）**
- `verified` このレビューは、提示された埋め込みテキスト（設計書抜粋・コード抜粋・profile抜粋）のみを根拠にしている（ファイル実読込なし）。
- `verified` 現行 Stage B 判定実装では、fold ごとに `fold_sharpe is None` を unavailable として集計し、全 unavailable 時に `all_folds_unavailable` を付与している（[stage_gate.py:530](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:530)）。
- `verified` Stage A threshold は config 読込時に `stage_a.threshold` から `cfg.stage_gate.stage_a_threshold` に入る（[config.py:375](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py:375)）。
- `verified` summary 出力は `cfg.stage_gate.stage_a_threshold` をそのまま書いている（[run_ga.py:876](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:876)）。
- `unverified` `history.jsonl` の threshold が実評価へ自動伝搬しているか（経路有無・優先順位）。
- `unverified` `all_folds_unavailable` の主因が trade_count ガードか、fold 構築不整合か、例外多発か。

**C9 反証先行（Round 1）**
- 反証1: 「原因は calibrate 伝搬不全のみ」  
  反証成立。Stage B 側だけで `all_folds_unavailable` が構造的に起きる実装経路が現にあるため、単一原因断定は不可。
- 反証2: 「trade_count_min_for_sharpe=30 が必ず犯人」  
  反証成立。`fold_exception` や bars/fold 構築不整合でも同じ表層症状になるため、現時点で確証不足。
- 反証3: 「state file メタデータ設計で contamination は十分防止できる」  
  反証成立。`config_hash` の定義次第で正当レコードまで弾く自己矛盾が起こり得る。

**指摘（Fact / Interpretation 分離）**

1. [Critical] 施策0の調査項目を現行アーカイブだけで完遂できない  
Fact: 現行 Stage B payload は `n_fold_unavailable` と bool 列相当のみで、unavailable の内訳理由を保持していない（[stage_gate.py:530](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:530)）。  
Interpretation: 施策0で求める `invalid_fold_count_by_reason` は、追加計測なしでは再構成不能。誤因果で施策Bを誤るリスクが高い。  
修正案: 施策0に「fold unavailable reason の計測追加（例: `fold_exception` / `trade_count_below_min` / `zero_variance` / `no_trades`）」を明示し、archive/run_reportへ保存する。

2. [Critical] 施策Aの `config_hash` ガード設計に自己矛盾リスク  
Fact: 設計案は `record.config_hash == compute_config_hash(cfg)` を必須化しつつ、同時に threshold override を適用対象としている。  
Interpretation: hash 対象に `stage_a_threshold` を含めると、前RUNで調整済みthresholdのレコードが次RUNで不一致になり、正当な伝搬まで fail-closed で落ちる。  
修正案: hash を 2 系統化する。`base_config_hash`（適応値を除外）で適用判定、`full_config_hash`（完全再現用）で監査。適用判定には `base_config_hash` を使う。

3. [Critical] 施策Bの修正候補に「閾値緩和ハック」混入余地  
Fact: 候補に `max(5, int(0.5 * wf_test_days))` のような経験式が含まれている。  
Interpretation: 統計的根拠なしの緩和は禁止事項4（見かけ改善）と衝突しうる。再発時に説明不能。  
修正案: 先に統計要件（Sharpe推定の最小サンプル根拠）を固定し、それを満たすために `wf_test_days`・指標定義・利用指標を設計側で再定義する。値だけ先に動かさない。

4. [Warning] 施策0の「コード変更なし」と「診断ログ追加」が矛盾  
Fact: 施策0冒頭はコード変更なし、0.2は `run_ga.py` へログ追加を要求。  
Interpretation: 実行計画が曖昧で、レビュー/監査時に手順不整合を生む。  
修正案: 施策0を `0a(純調査)` と `0b(計測パッチ)` に分割し、成果物とコミット粒度を明記する。

5. [Warning] state file 読込の型安全要件が不足  
Fact: 提案関数はメタデータ一致を重視しているが、`threshold` 値の finite/range 検証・schema_version 明記がない。  
Interpretation: 壊れた履歴で不正値適用のリスクが残る。  
修正案: `schema_version`、`isfinite`、許容レンジ、時刻フォーマット検証を必須化。不正時は fail-closed + reason ログ出力。

6. [Suggestion] V3 合格基準の統計仕様を固定  
Fact: `target ± tolerance` はあるが、seed数・許容幅算定ルールが未固定。  
Interpretation: 判定が運用者依存になる。  
修正案: seed本数、許容幅、判定ロジック（例: 3 seed 中 2 以上）を事前固定。

**施策別判定**
- 施策0（Investigation）: `REQUEST_CHANGES`
- 施策B（Stage B修正）: `INCONCLUSIVE`（施策0で原因分離が完了するまで）
- 施策A（calibrate伝搬）: `REQUEST_CHANGES`

**観点16/17**
- 16. Investigation主導設計の妥当性: `REQUEST_CHANGES`  
  理由: 調査項目は良いが、現行データだけでは識別不能な指標があり、計測追加が前提条件として不足。
- 17. state file 型適用の安全性: `REQUEST_CHANGES`  
  理由: contamination防止メタデータの方向は正しいが、`config_hash` 定義・schema/version・値検証が未確定。

**全体判定**
- `CHANGES_REQUESTED`

**補足（最初の F1-F7 論点の要約）**
- F1 bars_scale 4.29: `INCONCLUSIVE`（14日実行だった可能性は高いが、Stage A 実バー長の実測ログで確定が必要）
- F2 on_bar差分0.69s: `APPROVE(仮説)`（dict/loop/重複計算の寄与は大きいが、全部が削れる前提は過大）
- F3 Numba隠れコスト: `REQUEST_CHANGES`（worker並列時の初回compile/キャッシュ挙動を実測項目化すべき）
- F4 fastmath=False同値性: `REQUEST_CHANGES`（bit-identical主張は過剰。allclose基準へ統一）
- F5 T037不変性: `APPROVE(条件付き)`（`!=0.0` 判定再現テストを必須化）
- F6 Stage B/C線形効果: `INCONCLUSIVE`（共有経路は事実だが線形主張は強すぎる）
- F7 メモリ概算: `APPROVE(概算)`（大枠妥当。ただし gate配列・同時保持分を含むピーク実測を追加）