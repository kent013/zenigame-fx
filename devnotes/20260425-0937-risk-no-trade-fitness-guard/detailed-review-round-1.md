**前提検証 (C4)**
- Verified: Stage A の `trade_count<1` で `fitness_pen=None` になり、archive 側で `0.0` フォールバックされ、GA 選択 tie-break に使われる因果列は実コードと一致しています。  
[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L303) / [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L212) / [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L338) / [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L111)
- Verified: `_select_best` のシグネチャは設計案の呼び出しと整合しています。  
[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L470)

**施策ごとの判定**

1. 施策1: Stage A sentinel化 + `min_exposure_trade_count`  
判定: **REQUEST_CHANGES**  
- [Critical] `min_exposure_trade_count < live_criteria.trade_count_min` を不変条件にすると、既存の `trade_count_min=0` 構成が壊れます（現行テストfixture/テストコードで実在）。  
  修正案: 不変条件を `min_exposure_trade_count >= 1` は維持しつつ、上限制約は `trade_count_min >= 1` の場合のみ適用するか、`<=` に緩和して `trade_count_min=1` を許容してください。  
  参照: [alpha_factory_min_config.yaml](/Users/ishitoya/repository/zenigame-fx/tests/fixtures/alpha_factory_min_config.yaml#L25) / [test_stage_gate.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate.py#L705)
- [Warning] `fitness_raw` を sentinel 化する方針は妥当ですが、`fitness_raw=「ペナルティ前 sharpe」` という既存意味論とのズレを明文化しないと後段レポート解釈で混乱します。  
  修正案: SSOT/用語に「失敗時は sentinel を取り得る」を追記。

2. 施策2: config loader 経路  
判定: **REQUEST_CHANGES**  
- [Critical] 施策1の不変条件問題をそのまま loader で顕在化させるため、現行 fixture や一部運用オーバーライドが読み込み不可になります。  
  修正案: 施策1の不変条件修正とセットで loader も実装してください。  
  参照: [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L261)

3. 施策3: calibrate_gate sentinel 除外  
判定: **REQUEST_CHANGES**  
- [Critical] pool だけ sentinel 除外し `n_used` をフィルタ前のままにすると、`min_sample_size` を満たしたように見えて実際は極小サンプルで quantile 更新が走る可能性があります。  
  修正案: `fitness_pen_pool` の有効件数（例: `n_pool_used`）を別管理し、`decide()` のサンプルサイズ判定に使ってください。  
  参照: [calibrate_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L317) / [calibrate_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L518)
- [Warning] `all_sentinel` を `skip_zero_variance` 扱いにすると原因分類が不正確です。  
  修正案: `pool` 有効件数不足は `skip_sample_size` へ寄せる。

4. 施策4: docs SSOT 更新  
判定: **APPROVE**  
- [Suggestion] `stage-gates.md` だけでなく、`fitness_raw` 意味論を持つ関連文書にも注記を足すと将来の誤読を防げます。  
  参照: [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L28)

5. 施策5: テスト更新/追加  
判定: **REQUEST_CHANGES**  
- [Warning] `no_trades -> no_exposure` の置換漏れリスクが残っています（既存テスト内の集合assert等）。  
  修正案: `no_trades` 文字列の全検索と、優先順位テスト（`system_failure > no_exposure > metric_unavailable`）を追加してください。  
  参照: [test_stage_gate.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate.py#L394)

6. 施策6: run_ga 回帰テスト  
判定: **REQUEST_CHANGES**  
- [Critical] 提案テストは `_select_best` に sentinel を直接注入しており、元不具合経路（`Stage A -> archive 0.0 fallback -> cache`）を再現しません。fail-first にならないため回帰テストとして弱いです。  
  修正案: `evaluate_stage_a`（no-tradeケース）→ `collect_stage_a` → `_update_cache` → `_select_best` の統合経路を検証するテストに変更してください。  
  参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L440)

**追加観点**
- 実装モード（incremental）は妥当: **APPROVE**
- ルックアヘッドバイアス（#9）: primitive変更ではないため **INCONCLUSIVE（N/A）**
- メモリ制約（#10）: 追加コストは軽微で **APPROVE**
- 並行計算経路（C2）: `_select_best` だけでなく `_tournament`/elite sort も同一比較軸なので、経路テスト追加を推奨: **REQUEST_CHANGES**
- collider bias / sample size（C3/C7）: 相関因果の主張は抑制されており方向性は適切。ただし施策3の有効サンプル定義は要修正: **REQUEST_CHANGES**

**全体判定**
- **CHANGES_REQUESTED**

補足: 今回は静的レビューのみで、テスト実行はしていません。