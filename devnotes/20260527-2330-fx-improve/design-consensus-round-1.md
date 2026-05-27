1. 結論: 現時点で「低DOF regime primitive 追加」の正の期待値は低く、採用に値する直交信号は実務上ありません。  
理由は、`M1(vol)`・`M2(session)`・`M6(trend)`が既に同一探索空間で長期間フル探索され、`R101 frontier=723`がその包含空間で達成済みだからです。ここに近傍の1-2 param OHLCゲートを足しても、情報直交性より相関重複と探索希釈のリスクが勝ちます（過去の構造施策の実証負けとも整合）。

2. はい、**総括 D' を最終化**すべきです。  
AGENTS.md 追記1文案:  
`regime 条件（vol/session/trend）は default 32 primitive（M1 ATRRegimeGate, M2 SessionGate, M6 TrendStrengthGate）で既に探索空間へ実装済みであり、frontier（sharpe1.5/pnl70k/dd2%/trade50/pfr0.4, R101=723個体@ann5.58）はその包含空間で達成された運用上限として扱う。`  
以後の運用: improve-cycle は「構造拡張RUN停止・monitoring/shadowのみ」に切替し、`データ前提の変更`（新データ種/市場構造変化/評価契約変更）が起きるまで凍結。

3. 次の一手は1つに収束: **D'最終化のガバナンス固定**（AGENTS.md/runbookへ明文化し、構造RUN凍結ルールを運用既定化）。  
EVは最も高く、実装コストは最小、過去の負の結果と矛盾しません。

全体判定: **総括D'最終化（低DOF regime追加は不採用、frontierを最終達成上限として固定）**。