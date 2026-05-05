# Round 2 Design Review

## C2 (絞り込み版) 判定
**APPROVE** - 「1反証可能仮説 (H1) + 1最小変更 (M1: `collect_stage_a` の `total_pnl` 伝搬 + 回帰テスト1本)」に収束しており、cycle 1 原則を満たしています。  
現行実装上も `collect_stage_a` で `total_pnl` 未設定のため、仮説と変更点は因果が一直線です。

## C1/W3 持ち越し評価
**APPROVE** - 妥当です。  
C1 は run-34 artifact 互換性未検証のまま監査根拠に使わない判断が正しいです。  
W3 は nullable契約・現行schema非搭載項目を cycle 1 で無理に扱わないのが適切です。

## リスク管理 (Stage A 単独修正で B/C と矛盾) 評価
**APPROVE** - 「実装時に `collect_stage_b/c` を確認するが、修正は最小に留める」方針で十分です。  
補足推奨として、成功条件の比較対象は「Stage A時点の行（または Stage B/C 未評価個体）」に限定明記すると判定ぶれを避けられます。

## 全体判定
**APPROVED**

## 主要指摘 / 推奨事項
- Blockingな追加修正はありません。
- 非blocking推奨: success criterion 1 の比較条件を「Stage A時点」に限定して明文化。