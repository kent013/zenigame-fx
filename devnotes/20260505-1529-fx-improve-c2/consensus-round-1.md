# Round 1 合議結果

## P1 (Stage B WF 窓設計契約化)
- 判定: **APPROVE**
- 分類: **Structural（主） + Principled Parametric（従）**
- 妥当性評価:
  - `target_metric / failure_mode / causal_path / falsification / success_criterion` は一貫しており、C4（前提検証）にも適合。
  - 「fold不足が構造起因」という仮説は反証可能で、C9にも適合。
  - 禁止事項 1/2/4/6/7 への抵触はなし。ただし WF 値変更は「幾何契約を満たす最小変更」に限定し、場当たり tuning にしないこと。
- 因果ループ:
  - **切断なし**。上流（partition契約）を先に固定してから下流（WF窓）を調整する順序は正しい。
- 実装範囲の絞り込み案 (cycle 2 「最小変更」原則):
  1. `validate_stage_b_window` 追加（契約違反は RuntimeError fail-closed）
  2. `wf_*` を「fold>=5 を満たす最小セット」に変更（例は20/5/5だが、実データで算出して確定）
  3. 起動ログに「必要最小bars / 実bars / 算出fold」を明示（監査可能化）

## P2 (Stage B pass 品質監査)
- 判定: **MODIFY**
- 分類: **Structural（分析ガード）**
- 妥当性評価:
  - 問題提起は妥当。ただし `success_criterion` の「40+帯で mean positive」は n が小さい場合に過剰（C7/C8）。
- 修正提案:
  - cycle 2 は分析のみ維持。
  - 判定は「層別後も Stage B pass 優位が再現するか」を主軸にし、`INCONCLUSIVE` を明示許容。
  - 効果量（中央値差・符号率）を併記し、mean 単独評価を避ける。

## P3 (selection_score_schema 感度分析)
- 判定: **MODIFY**
- 分類: **Reactive Parametric（分析限定で許容）**
- 妥当性評価:
  - 現RUNで best が Stage A only なので、即 schema 変更に進む因果は弱い。
  - C2（「Xが無い=バグ」禁止）と C6（Fact/Interpretation分離）の観点で、まず実測監査に限定すべき。
- 修正提案:
  - cycle 2 は「上位占有率の実測監査のみ」。
  - schema 改変は cycle 3 以降、P2 と整合した時のみ検討。

## P4 (per_generation observability)
- 判定: **APPROVE**
- 分類: **Structural**
- 妥当性評価:
  - 計測ロジック不変で観測性のみ改善するため、過学習リスクが低い。
  - 禁止事項 1/2/4/6/7 への抵触なし。
- 実装範囲の絞り込み案:
  1. 7/8 key の null 原因を経路別に特定
  2. 出力スキーマへの埋め戻し（計算値は既存値を再利用）
  3. null率レポートを run 終了時に自動出力

## P5 (reason_code 集計正規化)
- 判定: **REJECT（cycle 2 では見送り）**
- 分類: **Structural（だが優先度低）**
- 妥当性評価:
  - 方向性は正しいが、今回の CRITICAL_DRIFT 収束に対する寄与が間接的。
  - cycle 2 の最小変更原則に対してスコープ超過。
- 扱い:
  - 保留（cycle 3 以降の可観測性改善バッチに統合）

## 総合
- cycle 2 で実装すべき施策一覧 (Critical 1-2 + Warning 1-2)
  1. **P1-1** Stage B window 契約 guard の実装（fail-closed）
  2. **P1-2** WF 窓の幾何整合化（fold>=5 を満たす最小変更）
  3. **P4** per_generation 観測経路の補修（null率<10%）
  4. **P2(分析のみ)** trade_count 層別監査の追加（INCONCLUSIVE許容）
- 却下されたもの一覧
  1. **P5** reason_code 正規化（cycle 2 では実装しない）
- 保留事項
  1. **P3** selection_score_schema 改変は監査結果待ち
  2. P2 の統計的十分性（n<30）により結論は暫定扱い

## 全体判定
**APPROVED**