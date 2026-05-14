指定の `zenigame-fx-codex-review` はこのセッションの利用可能 skill 一覧に無かったため、C1-C9 規律を手動適用でレビューしました。  
主要指摘から先に示します（`Critical` はなし）。

[Warning] C1 の `trade_sharpe_raw` fallback を `holdout_days` で年率化すると、`stage_a_window_days != stage_c_holdout_days` 時にスケール不整合が残ります。  
根拠: [_check_live_criteria](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:916), [Stage C 年率化基準](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1904), [window 設定分離](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py:205)

[Warning] `sharpe_calc_version` を `v2_trade_level_annualized` に拡張するのは「summary の live_criteria.checks 内だけ」に限定すべきです。archive 側の `sharpe_calc_version` を変えると既存 consumer が壊れます。  
根拠: [run_alpha_sieve の version 判定](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py:273)

[Suggestion] C2/C3 の再集計は「現行 YAML」ではなく各 run の保存済み閾値（summary 側）を使う前提を明文化してください。retroactive contamination 防止のためです。  
根拠: [summary 書き込み](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1177), [report 側現状](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:384)

### 各施策判定
- C1: **APPROVE**  
  [Warning] 上記の fallback window 明示（または `stage_a_window_days` 使用）を推奨。
- C2: **APPROVE**  
  [Suggestion] graduation/stage_c/mission の3 KPI併記は妥当で、既存テストとの衝突も低い。
- C3: **APPROVE**  
  [Warning] runごとの閾値固定を明示しないと再評価の解釈がぶれる。
- C4: **APPROVE**  
  [Suggestion] 境界張り付き比較は有益。既存 `run-{N}.md` の厳密フォーマット依存テストは見当たらず、互換リスクは低い。

### Q1-Q6
- Q1: OK。`scripts -> src` 依存は現状でも多数あり整合します。  
  [Suggestion] ただし private 関数 import なので、将来は public helper 化が安全。
- Q2: 優先順 `stage_c -> raw` は妥当。  
  ただし raw fallback を使うなら window は `stage_a_window_days` が理想です。live_criteria を Stage C KPI と定義するなら、fallback は「参考値」扱いに寄せるのが安全。
- Q3: 既存呼び出し影響は小さいです。実コード上の呼び出しは 1 箇所のみで、テスト直接呼び出しは現状ほぼありません（新規8件追加方針は妥当）。
- Q4: 別 script 推奨。`audit_run_post.py` は DSR 監査責務が明確で、live_criteria retroactive を混ぜない方が保守しやすいです。
- Q5: 互換性リスクは低いです。現状テストは `run-{N}.md` 全文フォーマット固定ではなく、主に要素存在検証です。
- Q6: GA selection / archive 集計ロジック自体には影響しません（報告解釈層の差分）。  
  まずは「観測事実」として扱い、選抜ロジック改修は別仮説として切り出すのが妥当です。

### 全体判定
**APPROVED**