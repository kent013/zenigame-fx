# Round 1 合議結果

## P1 (Stage partition/holdout 実測監査)
- 判定: **APPROVE**
- 分類: **Structural**
- 追加観点:
  - `target_metric/failure_mode/causal_path/falsification/success_criterion` は一貫しており妥当。
  - まず契約（T087）と実測の一致確認を行うのは因果ループ切断の防止として正しい。
  - 禁止事項 1/2/4/6/7 への抵触: **なし**（設計契約起点、Fact優先、反証可能）。

## P2 (total_pnl=0.0 計測経路チェック)
- 判定: **APPROVE**
- 分類: **Structural**
- 追加観点:
  - `sharpe>0` かつ `trade_count=67` で `total_pnl=0` は計測経路異常の強いシグナル。最優先で妥当。
  - falsification（ローカル再評価＋ledger再集計）が明確で、成功条件も検証可能。
  - 禁止事項 1/2/4/6/7 への抵触: **なし**（観測事実→経路検証で、パラメータ先行調整を回避）。

## P3 (Stage A 選別力厳格化実験)
- 判定: **MODIFY**
- 分類: **Principled Parametric**
- 修正案 (MODIFY 時):
  - **前提条件付き承認**に変更: P1/P2 完了後に実施。
  - 最小変更は `stage_a.threshold` 単独変更のみ（他パラメータ固定）。
  - 成功基準を「`Stage B pass数が不変以上`」だけでなく「`Stage B reason_code 構成の改善`」を追加。
- 追加観点:
  - 現時点で計測系が不確実なため、先行実施は因果ループを切るリスク。
  - 禁止事項 1/2/4/6/7: **現状のまま実行すると4/6/7に抵触リスク**（計測未確定で解釈先行）。

## P4 (max_clause=2 寄与仮説 A/B)
- 判定: **REJECT**（cycle 1 対象外）
- 分類: **Reactive Parametric**
- 却下理由 (REJECT 時):
  - 探索空間拡張は計測不整合（P1/P2未解決）下では効果判定不能。
  - `active_clause=1` は結果であり原因確定ではない。現時点では collider/confounding の疑いが強い。
  - cycle 1 の「最小変更」原則に反する。
- 追加観点:
  - 禁止事項 1/2/4/6/7: **抵触リスク高**（反証前に探索軸追加、解釈先行）。

## P5 (cross-pair shadow multi-instrument 検証)
- 判定: **REJECT**（cycle 1 対象外）
- 分類: **Reactive Parametric**
- 却下理由 (REJECT 時):
  - 単一instrument runの診断フェーズで軸追加すると、P1/P2 の根本原因切り分けが不可能になる。
  - 因果経路が長く、cycle 1 の収束条件（1仮説+最小変更）を破る。
- 追加観点:
  - 禁止事項 1/2/4/6/7: **抵触リスク高**（同時変更による因果同定不能）。

## 総合
- cycle 1 で実装すべき施策一覧 (Critical 1-2 件 + Warning 1-2 件)
  - Critical 1: **P1 実装**（partition/holdout の timestamp 実測監査、disjoint 証跡出力）
  - Critical 2: **P2 実装**（trade ledger→summary までの `total_pnl` 集計経路の突合）
  - Warning 1: **P3 は前提付きで設計のみ**（P1/P2 完了後に threshold 単独変更試験）
  - Warning 2: **archive/per_generation null 多発の記録整備**（観測性改善。パラメータ調整はしない）
- 却下されたもの一覧
  - **P4, P5**（cycle 1 では非採用）
- 保留事項 (検証期限付き)
  - P3: **P1/P2 修正完了直後の次runまでに**再判定
  - P4/P5: **cycle 2 以降**、P1/P2 収束後に再エントリ可

## 全体判定
**CHANGES_REQUESTED**（理由: cycle 1 は **P1+P2 の構造検証に収束**させるべき）