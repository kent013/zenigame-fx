## 判定

NEEDS_REVISION

## 前提（C4）

- 実装者がまず参照する主仕様は `conceptual-design.md` である  
- `docs/alpha_factory/concepts/alpha-sieve.md` は概念SSOTとして主仕様と矛盾しない必要がある  
- Phase 2 では DSR は monitor-only を許容する

## 反証検討（Falsification-first）

- **H1 反証論点**: 取引日が偏在すると `trade_count>=30` でも小標本バイアスは残る  
  反証成立条件: 少数日に取引集中。  
  抑制要素: `trade_count>=30` へ引上げ、DSR併記（ただし hard gate ではない）。
- **H2 反証論点**: ドキュメント内の窓定義不整合で実装が旧仕様に戻る  
  反証成立条件: 実装者が旧記述を採用。  
  抑制要素: §2.2 は正しく `embargo=5` を定義済み。
- **H3 反証論点**: `sharpe>0.5` は有意性保証ではない  
  反証成立条件: 非正規・ファットテールで推定誤差大。  
  抑制要素: DSR監視追加、Phase 4 hard化方針を明記。

## 観点別評価

1. OOS 期間の妥当性: **概ね解消**。ただし旧仕様記述が残存。  
   - 旧記述: OOS が `holdout_end + 1d ~ +90d` のまま  
     [conceptual-design.md:43](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/conceptual-design.md:43)
2. 通過基準の妥当性: **ほぼ解消**。`trade_count>=30` は妥当な一次防御。  
   - ただし同ファイル内に旧基準 `>10` が残存  
     [conceptual-design.md:44](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/conceptual-design.md:44)
3. defensive 設計: **解消**。`status`/`no_data` 詳細/exit方針は十分。  
   - [conceptual-design.md:99](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/conceptual-design.md:99)
4. 学術引用: **部分解消**。embargo/CSCV拡張方針は主仕様に明記済み。  
   - [conceptual-design.md:62](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/conceptual-design.md:62)  
   - ただし concept stub 側に「CSCV簡易版」明示が不足  
     [alpha-sieve.md:60](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/alpha-sieve.md:60)
5. スコープ境界: **解消**。Phase 4 deferred の切り分けは妥当。  
   - [conceptual-design.md:240](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/conceptual-design.md:240)

## 修正要求（最小）

- `conceptual-design.md` §2.1 の処理説明を新仕様に同期（`+5d embargo`、`trade_count>=30`）。  
- 同ファイル末尾のレビュー観点の旧式文言（`+1~+90` / `>10`）を更新。  
  [conceptual-design.md:256](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/conceptual-design.md:256)
- `alpha-sieve.md` に「Phase 2 は CSCV 簡易版（単一追加OOS）」を明示。