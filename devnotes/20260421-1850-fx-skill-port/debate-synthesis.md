# FX GA アーキテクチャ — Claude × Codex 3 ラウンド議論の統合

**作成日時**: 2026-04-21 20:35 (JST)
**モデル**: Claude Opus 4.7 (1M context) × GPT-5.3 Codex (xhigh reasoning)
**議論回数**: 3 ラウンド（セッション継続）
**元ファイル**:
- [Round 1 プロンプト](.codex-prompt-arch-debate-round-1.md) / [Round 1 結果](codex-arch-debate-round-1.md)
- [Round 2 プロンプト](.codex-prompt-arch-debate-round-2.md) / [Round 2 結果](codex-arch-debate-round-2.md)
- [Round 3 プロンプト](.codex-prompt-arch-debate-round-3.md) / [Round 3 結果](codex-arch-debate-round-3.md)

---

## 議論の全体構造

### Round 1 — Falsification-first（4 論点）
Claude の暫定推奨 **(b) Clause × (i) per-instrument** に対し、Codex に反証を探させた。

- **Q1. Clause 構造は FX で有効か?** → CONDITIONAL / MEDIUM。有利 (regime 切替) と不利 (1 銘柄学習で bloat) が並立。
- **Q2. 銘柄特化 GA は妥当か?** → CONDITIONAL / MEDIUM。FX 6 ペアでも USD 共通因子あり、universal ベースライン併走が必要。
- **Q3. 中間案（universal eval）** → SUPPORT / HIGH。常設ベンチマークとして組み込むべき。
- **Q4. 1 銘柄 OOS の検出力** → CONDITIONAL / MEDIUM。DSR / PBO / Reality Check 必須。

**Round 1 総合判定**: **(b)×(i) 採用可、ただし (ii-lite) 常設ベンチマーク並走が条件**

引用された主要文献:
- Koza (1992), Poli et al. (2008) — GP bloat 管理
- Allen & Karjalainen (1999) — FX GP 古典
- Jacobs et al. (1991), Jordan & Jacobs (1994) — Mixture of Experts（Clause 構造の理論背景）
- Evans & Lyons (2002) — FX order flow（セッション依存性）
- Asness et al. (2013) — Value and Momentum Everywhere
- Menkhoff et al. (2012), Lustig et al. (2011) — 通貨共通因子
- White (2000), Hansen (2005) — Reality Check / SPA
- Bailey et al. (2014) — Probability of Backtest Overfitting
- Bailey & López de Prado (2014) — Deflated Sharpe Ratio
- López de Prado (2018) — Advances in Financial ML（purging/embargo）

### Round 2 — 実装具体化（5 論点）
Round 1 の CONDITIONAL 条件を具体的な数値・式・閾値に落とし込んだ。

- **Q5. Clause 複雑度制約** → max_clause=2 デフォルト（3 は条件付き）、ペナルティ α=0.03-0.08、size_norm 式提示
- **Q6. (ii-lite) 常設ベンチマーク設計** → B2 ゲート、アンカー3ペア、`F = mean(Sharpe_i) - 0.5*std(Sharpe_i)`
- **Q7. 移行トリガー定量化** → DSR<0 3連続、PBO>0.5、m/N>=0.4、RC p>0.10 の複合
- **Q8. Currency common factor** → β（評価フィルタ）→ α（DSL 変数）→ exposure 制約の段階導入
- **Q9. MVP 実装順序** → max_clause=1→2→3 段階、shadow→hard gate、移行トリガーは実装して発動保留

**Round 2 総合判定**: **STILL_VALID + 3 点修正**

### Round 3 — 前提値 stress test と最終統合（5 論点）
Round 2 の疑わしい前提を stress test して最終仕様を確定。

- **Q10. n_eff 再検証** → Q5 の `n_eff≈250` は過度保守的。実測レンジ 1,000-10,000 が妥当、α は `n_eff` 連動
- **Q11. DSR/PBO/RC 実装コスト** → DSR Phase 2、PBO-lite Phase 3、RC/SPA Phase 4 の段階実装で現実化可能
- **Q12. max_clause=1 の意義** → 初日から directional/gate 分離・正規化・ヒステリシスを実装すれば「フラット同値」回避可
- **Q13. shadow→hard gate 化判定** → 30 run + 各 target 5 run + 通過率 30-70% + 予測力 +0.15 / p<0.10
- **Q14. 6 ペアアンカー具体化** → target 別に 2 アンカー指定、USD_ZAR は除外せず最後の robustness test 用

**Round 3 総合判定**: **最終仕様確定**

---

## 最終仕様（実装に渡せる粒度）

### A. ゲノム構造仕様

| 項目 | 値 | 備考 |
|------|-----|------|
| max_clause | 初期 1 → 標準 2 → 上限 3 | 昇格試験合格時のみ 3 |
| max_depth | 5 | 合成式深さ |
| directional signal 加重和 | `Σ w_i × x_i / Σ\|w_i\|` | 必須 |
| local_gate | `[0, 1]` sigmoid 有界 | 必須 |
| clause_weight 正規化合成 | `Σ(cw_k × cs_k) / Σ\|cw_k\|` | 必須 |
| composite hysteresis | entry θ_on > exit θ_off | 必須 |
| session close / time_stop | min/max保有時間 | 必須 |
| spread / slippage フィルタ | コスト反映 | 必須 |
| long/short 対称制御 | パラメータは分離可 | FX 必須 |

### B. Stage A/B/C 仕様

| Stage | 期間 | 通過率目標 | ペナルティ / 基準 |
|-------|------|-----------|-----------------|
| A (Fast Screen) | 直近 60 営業日 | 15% (10-20%) | α_A = 0.03（n_eff 連動で 0.02-0.05） |
| B (Full IS + WF-OOS) | 過去 18 ヶ月 / WF: train 120d, test 20d, step 20d, embargo 1d | Top-K | median OOS Sharpe ≥ 0.20、正 fold ≥ 60%、DSR ≥ 0（初期 monitor） |
| C (Live Criteria + Stress) | holdout | — | live_criteria + (ii-lite) + spread×1.5 stress + trade 50-5000 |

### C. (ii-lite) Cross-pair 評価

**評価ペア**: target + アンカー2ペア（target ごとに固定、Q14 表）
**主目的関数**: `F = mean(Sharpe_i) - 0.5 × std(Sharpe_i)`
**監査関数**: `min(Sharpe_i)`, 流動性重み付き mean
**通過基準（AND）**:
1. `Sharpe_target_cross ≥ 0.8 × Sharpe_target_single`
2. `mean Sharpe_cross ≥ 0.15`
3. `min Sharpe_cross ≥ -0.20`

**アンカー定義（target → アンカー2）**:
| target | アンカー |
|--------|---------|
| EUR_JPY | {EUR_USD, USD_JPY} |
| USD_JPY | {USD_CAD, EUR_JPY} |
| EUR_USD | {EUR_JPY, USD_CAD} |
| AUD_JPY | {USD_JPY, EUR_USD} |
| USD_CAD | {USD_JPY, EUR_USD} |
| USD_ZAR | {USD_CAD, USD_JPY} |

**improve-cycle 主力順序**: `EUR_USD → USD_JPY → EUR_JPY → AUD_JPY → USD_CAD → USD_ZAR`

### D. 統計検定インフラ

| カテゴリ | 内容 | Phase |
|---------|------|-------|
| 必須 | DSR, fold 符号反転率, block bootstrap Sharpe CI | 2 |
| 段階実装 | PBO-lite (top-M=20, S=6-8) | 3 |
| 後回し可 | RC/SPA フル実装（B=1000 標準, 3000 重要判定） | 4 |

### E. Phase 別実装スコープ

**Phase 2 MVP（必須）**:
1. Clause エンジン（max_clause=1 開始、directional/gate 分離、正規化、ヒステリシス）
2. Stage A/B/C 最小パイプライン（WF-OOS 必須）
3. archive（instrument, complexity metrics, gate metrics）
4. (ii-lite) shadow 評価（非ブロッキング）
5. DSR + 符号反転 + bootstrap CI

**Phase 3**:
1. max_clause=2 標準化、3 の昇格試験
2. 共通因子 α (DSL 変数) / β (評価フィルタ) 段階導入
3. PBO-lite 実装

**Phase 4**:
1. (ii-lite) hard gate 化
2. RC/SPA 実装
3. rollback 自動化
4. (b)×(i)→(ii) 移行トリガー自動判定

### F. 移行トリガー（最終版）

**(b)×(i) → (ii) hard 移行**:
- `PBO > 0.5` AND (`DSR < 0` 3 連続 OR fold 負比率 ≥ 0.4)
- または `RC/SPA p > 0.10` 3 連続 + DSR 改善なし

**(ii-lite) shadow → hard gate 化**:
- ウォームアップ: 30 run 以上 AND 各 target 5 run 以上
- 安定性: 通過率 median 30-70%、std ≤ 15pp
- 予測力: shadow 通過群の事後 OOS Sharpe 中央値が不通過群より +0.15 以上、検定 p < 0.10

**rollback（hard → shadow）**:
- hard 化後 10 run 以内に target Sharpe が shadow 期基準比 25% 以上低下 × 2 窓連続
- または通過率 < 10% / > 90% が 10 run 連続

**判定不能時**: 60 run で discrimination 不成立なら永久 shadow で運用

### G. 残課題（実測でしか決まらない）

1. `n_eff` の実測レンジ（bar / trade 両軸）
2. ペナルティ α の最終キャリブレーション（`n_eff` 連動係数）
3. アンカー感度（target ごとの効果差）
4. USD_ZAR の実運用コストモデル妥当性
5. RC/SPA の計算予算上限（実行時間基準）

これらは Phase 2-3 で実データを取った後に仕様を確定する。

---

## 最終決定

### ✅ 軸 1: (b) Clause ベース合成を採用

- `src/dsl/genome.py` を WhenConfig + HowConfig 構造に再構築
- clause_score = dir_score × gate の合成、composite で売買判定
- FX primitives（TrendEMA, RSIRevert, BollingerRevert, SessionGate, ATRRegimeGate 等）を FX 用に再定義

### ✅ 軸 2: (i) per-instrument GA + (ii-lite) shadow 並走

- `improve-cycle` は `--instrument` 第一級パラメータ
- archive に `instrument` カラム、cross-pair 分析は横断クエリで
- (ii-lite) shadow は Phase 2 から常時実行、Phase 4 で hard gate 化

### ✅ 実装優先度

1. Phase 2 で MVP を動かす（Clause 骨格 + Stage A/B/C + DSR + shadow eval）
2. Phase 3 で複雑化（max_clause=2/3 解放 + 共通因子 + PBO-lite）
3. Phase 4 で完成（hard gate + RC/SPA + rollback + 移行トリガー自動化）

### 移行パス

この設計が機能しない場合の次の手:
1. (b)×(i) → (ii) 完全移行: 移行トリガー発動時
2. (b)×(i) → (iii) Portfolio GA: 三角裁定制約が運用上問題化した場合
3. (a) フラット式への後退: Clause 構造が bloat で破綻した場合（複雑度ペナルティ失敗）

---

## 次のアクション

1. **ga-architecture.md を本仕様で上書き**: 前版の「未決事項」セクションを削除し、確定仕様に差し替え
2. **design.md を修正**: Phase 2-4 のスコープを本仕様に合わせて詳細化
3. **Phase 0 から着手**: まず DROP 7 skill を `.claude/skills/_archived/` に退避
