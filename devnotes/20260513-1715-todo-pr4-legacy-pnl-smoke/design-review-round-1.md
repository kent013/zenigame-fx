**前提（C4）**
- Fact: 本レビューは提示テキストのみを対象に実施（実コード未照合）。
- Fact: Codex Y Round 3-5 原文は未提示のため、整合判定は「設計書内の再掲式」に対する一致確認。
- Interpretation: 「設計品質レビュー」としては十分だが、「実装一致レビュー」は別途必要。

**主要指摘（Falsification-first, C9）**
- [Critical] sentinel経路の不変性検証が不足。`no_exposure` しか明示されておらず、`system_failure` / `metric_unavailable` で `legacy_pnl_smoke` が完全skipされる保証が弱い。  
  対象: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py), [test_stage_gate.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate.py)
- [Critical] 境界テストが未網羅。`total_pnl==12000`、`max_dd_pct==0.5`、`trade_count==80`、`max_dd_pct==1e-9` の等号境界が不足。初回行動変更PRとしてはここが欠落すると回帰リスクが高い。  
  対象: [test_stage_gate.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate.py)
- [Warning] rollback条件の「baseline median」の定義が曖昧（単一baseline run比較と矛盾）。判定手順を固定しないと運用時に恣意性が入る。
- [Warning] 設計文中で「persistence_weightをpayload記録」とあるが、payload追加項目に明示されていない。将来migration監査の再現性が落ちる。
- [Suggestion] C6/C7対応として、相関（ρ）記述は「因果でなく関連」と明記済みテンプレート化を推奨。

**セクション別判定**

**概念設計 §1-6**
- §1 背景/現状認識: 判定 `Pass`（課題設定は妥当、mission不整合の問題提起は一貫）
- §2 目的/opt-in理由: 判定 `Pass`（default OFF + rollback即時性は妥当）
- §3 推奨式: 判定 `Pass with Warning`（再掲式は整合、ただし等号境界仕様をテストで固定要）
- §4 期待効果: 判定 `Pass with Warning`（効果仮説は妥当、因果主張は抑制表現を維持）
- §5 スコープ縮小/非目的: 判定 `Pass`（M規模で最小スコープ）
- §6 リスク/検証戦略: 判定 `Needs Fix`（baseline定義・判定プロトコル明文化不足）

**詳細設計 §1-4**
- §1 config.py: 判定 `Pass`（4段伝搬の入口として整合）
- §2 stage_gate.py: 判定 `Needs Fix`（sentinel不変契約の担保がテスト要件まで落ちていない）
- §3 default.yaml: 判定 `Pass`（legacy defaultで行動不変契約に合致）  
  対象: [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml)
- §4 tests: 判定 `Needs Fix`（境界・sentinel網羅が不足）

**受入基準**
- 判定 `Needs Fix`
- [Critical] 受入基準に `system_failure` / `metric_unavailable` のlegacy一致を追加すべき。
- [Warning] 「payload監査項目（mode/beta/persistence/hard/soft）」の固定を追加推奨。

**smoke条件**
- 判定 `Pass with Warning`
- [Warning] C3対応として conditioning set（例: top decile定義、pair固定、seed固定）を明示すべき。
- [Warning] C8対応として 1 run で差が小さい場合は `INCONCLUSIVE` を許容する判定分岐を追記推奨。

**コミット計画**
- 判定 `Pass`
- [Suggestion] コミットメッセージに `default legacy (behavior invariant)` を明示して監査容易化。

**全体判定**
- `CHANGES_REQUESTED`

修正は小さく済みます。特に「sentinel 2経路の不変テスト追加」と「境界等号テスト追加」を先に入れれば、PR4の設計完成度は十分マージ可能水準です。