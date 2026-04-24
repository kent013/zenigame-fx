## 判定

NEEDS_REVISION

## 反証検討（Falsification-first）

- 仮説 H1（SieveでTPを1/2〜1/3に絞れる）
  - 最強の反証: 取引回数が少ない個体でも偶然の連勝で OOS Sharpe>0.5 を満たし通過してしまう（小標本ノイズ）。
  - 反証成立条件: OOSでの `trade_count` が小さい（例: ≤20）かつ分布が非正規・ファットテール、取引日の偏りが大きい。
  - 現設計の抑制点: `trade_count>10` を要求。ただし10は小さすぎ抑制不十分。
- 仮説 H2（60d holdoutと非対称な90d OOSでレジーム重複を避けられる）
  - 最強の反証: 為替レジームが四半期〜半期スパンで持続し、holdout直後90日も同一レジームに属してしまう（時間的非重複≠レジーム独立）。
  - 反証成立条件: マクロ主導の単一レジームが約5〜6か月以上継続。
  - 現設計の抑制点: 期間非重複のみ。レジーム独立性の担保（エンバーゴ/複数窓）は未実装。
- 仮説 H3（Sharpe>0.5はlive基準1.0のOOS劣化を見越した妥当な中間）
  - 最強の反証: 小標本ではSharpe推定誤差が大きく、0.5超過でも有意でない（選択バイアス・非正規性で過大評価）。
  - 反証成立条件: 実効独立試行数が小さい、取引リターンが歪度・尖度を伴う。
  - 現設計の抑制点: コスト反映とAND条件。ただしDSRや信頼区間の検定なし。

## 観点別評価

1. OOS 期間の妥当性: 部分的に妥当。時間的重複は排除できているが、holdout直後に連続配置するとレジーム持続時の独立性は弱い。López de Prado (2018) Ch.7 の「purged/embargoed CV」の趣旨からは、境界付近の依存を避ける短期エンバーゴ（数営業日）や、複数の非連続OOS窓の評価が望ましい。  
   要修正: 
   - `sieve_start = holdout_end + 1d` を `+5d` など短期エンバーゴ化（根拠: 時系列依存の境界効果低減）。
   - 将来Phaseで良いが、単一連続90日に加え「二分割45d×2」等の複数窓評価オプションを設ける旨を仕様に追記。

2. 通過基準の妥当性: 不十分。`trade_count > 10` はStage Cの`≥50/60d`に対し大幅に緩く、日次当たりでは約0.11件/日とサンプル不足リスクが高い。Sharpe>0.5は方向性として中間だが、小標本ノイズへの防御が弱い。  
   要修正:
   - `trade_count_min` を少なくとも `>=30` へ引上げ、または `>= max(30, ceil(0.5 * stage_c_trade_count))` の相対基準に変更。
   - 取引発生日数の下限（例: 非ゼロ取引日のユニーク日数 `>=15`）を追加し、偏在を抑制。
   - 可能なら指標の記録だけでも「Deflated Sharpe Ratio(DSR)」を計算し、通過判定は当面任意でも「DSR>0」を将来ゲート候補としてレポートに併記。

3. defensive 設計: 概ね妥当。`no_candidates`/`no_data`でexit 0は運用継続の観点では合理的。ただしオーケストレータ取り込みを前提に、機械可読なステータスをレポート先頭に明記すると良い。  
   要修正:
   - レポート先頭に `status: ok|no_candidates|no_data|error` を追加（将来のDB化・監視連携を容易化）。
   - `no_data` 発生時は「不足シンボル・期間」を列挙するセクションを追加。

4. 学術引用: 方向性は適切だが適用の具体が弱い。Bailey et al. (2014) のPBO/CSCVは「複数分割の検証で過学習確率を推定」する枠組みであり、単一の直後90日OOSのみでは本旨に届かない。López de Prado (2018) Ch.7 のpurged/embargoed CVも境界依存を避ける設計を推奨。  
   要修正:
   - 引用箇所に「本設計はCSC Vの簡易版として単一追加OOSを先行導入、Phase 4でpurged/embargoedやCSCVへ拡張予定」と明記。
   - 参考文献表記を明確化（下記参照、誌名は要確認）。

5. スコープ境界: 妥当。warmstart/score bypass/DB/レジーム別集計の後送りはPhase 2の負荷管理として合理的。将来移行を容易にするため、現時点でレポートに最小限のメタデータ（status/期間/閾値/バー件数/コスト仮定）を機械可読で残す設計を推奨。  
   要修正:
   - レポートに `criteria_snapshot`（sharpe_min/trade_count_min/total_pnl_min）と `cost_model`（スプレッド/スワップの扱い要約）をヘッダに固定出力。

参考文献（要確認）
- Bailey, D. H., Borwein, J. M., López de Prado, M., and Zhu, Q. J. (2014). “The Probability of Backtest Overfitting.” SSRN/Journal venue 要確認.
- López de Prado, M. (2018). “Advances in Financial Machine Learning.” Chapter 7: Cross-Validation in Finance.
- López de Prado, M. (2018). “The Deflated Sharpe Ratio.” SSRN 要確認.

