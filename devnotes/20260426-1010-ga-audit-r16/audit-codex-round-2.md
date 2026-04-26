# Round 2 — 合議結果

## 0. 前提（C4）
- [Verified] Run1-16 の Stage C が `spread_stress_skipped` 理由で一律失格となっており、`config/alpha_factory/default.yaml` に `max_spread_bps` 未設定であることが audit-codex.md / audit-claude.md で一致確認済み。
- [Verified] GA は trade-level Sharpe (v2) を fitness に用いている一方、`stage_a.threshold` および `live_criteria.sharpe_min` は bar-level 年率換算を前提とした旧スケールのまま残存している。
- [Verified] `RegistryEvaluator` 生成時に aux_map/snapshot が供給されず、pair-specific primitives が {0,0.5,1} の固定信号となっている点は両監査で確認済み。
- [Verified] mission の North Star は `live_criteria` を全て満たす Stage C 通過ゲノムを 1 個体発見すること、イントラデイ縛り/両建可/スプレッド・スワップ反映が絶対制約。
- [Verified] Round 2 では Claude 提案 (Sec A/B/C) に対する Codex 観点の同意・反証・追加論点を整理することがタスク。
- [Assessed] Phase0 完了前は RUN を追加実行しない方針が暫定合意されている（正式 DoD 未定義）。

## 1. Claude 同意点 (Sec A) への追加コメント
- A1 Stage C 恒久失敗: Stage C 再開後も `stress_multiplier` × `max_spread_bps` が下流コスト評価と乖離していないか検証する必要あり。`holding_cost_per_day_bps` を 0 に据え置く場合でも intraday 制約検証ロジックの網羅確認を併走したい。
- A2 Sharpe スケール乖離: 閾値更新時には trade-level Sharpe の分布推定に加え、`trade_count_min_for_sharpe` 近傍の個体で分散過小評価が起きないか (Lo 2002 の自己相関補正) を検証するのが安全。
- A3 aux データ不在: aux 注入後は null-safe fallback を設け、欠損ペアが GA をクラッシュさせないこと、さらに pair-specific が高頻度で選択され過ぎる場合の正規化設計（例: z-score vs raw）を再評価する必要がある。
- A4 plateau 反証: Stage A gate 再校正後も plateau が残る場合、mutation/operator 側の問題へ素早く切り替えるため、世代別 best fitness の再モニタリングと因果切断を続けるべき。
- A5 max_clause 拡張保留: Phase1 で clause 解放する際、初期世代の clause 分布と Stage A pass 率が同時追跡可能な telemetry を確保しないとフィードバックが遅れる点に注意。

## 2. 論点 B1〜B5 への独立解
- B1 閾値再校正: [Fact] trade-level Sharpe の直接比較は単位不一致。 [Interpretation] 閾値変更は「緩和」でなく「換算後同一基準維持」と文書化すれば禁止事項 #4 を回避できる。換算式は Section3(1) 案を採用し、docs に年間化ロジックと自己相関補正の前提を明記することで担保可能。
- B2 T037 順序: [Fact] T037 active-clause 計測は Stage A の archive だけで成立し Stage C pass を要しない。 [Interpretation] 依存無しなので Phase0 で並行実行可。ただし Stage C 再開前に得られる指標は「閉塞ゲート下の行動」である点を注記し、Phase0 後半で再測定して比較する運用が望ましい。
- B3 max_spread_bps: [Fact] EUR/JPY Tier1 で 1.0–2.0 pips が一般的。 [Interpretation] `max_spread_bps=10` (約1.0–1.5 pips) は妥当な初期値。通貨ペア差異はオプションとして `per_pair_overrides` を Phase1 で検討するが、Phase0 では共通値で開始し、metrics に spread 実測 (broker feed) を導入して後日補正する方針で問題なし。
- B4 mission_score: [Fact] live_criteria は4軸 (例: Sharpe, WinRate, Drawdown, TradeCount)。 [Interpretation] 当面 GA fitness に影響させず archive/report で連続監視する案に賛同。正規化は min-max もしくは logistic compression を用い、後述の幾何平均案で 0 付近を避ける。
- B5 RUN 凍結: [Fact] 現構造では Stage C pass = 0 が確定。 [Interpretation] Phase0 DoD 未達で RUN 17 を打つのは無益なので凍結に同意。DoD を明文化して improve-cycle gate に組み込むべき。

## 3. 確認事項 1〜6 への回答
- (1) 閾値再標準化換算式: Trade-level Sharpe `S_trade = μ_trade / σ_trade` とし、平均保有時間 `h̄`（日）、1営業年 252 日、平均日商回数 `λ_day` を用いて `S_annual ≈ S_trade × √(λ_day × 252 / (h̄ × adj_corr))`。`adj_corr = 1 + 2∑_{k=1}^{q}ρ_k` は Lo(2002) の自己相関補正。経験分布から `λ_day` と `h̄` を測定し、換算後閾値を docs に固定。「trade-level 値を外形的に引き下げるのではなく、年率換算した値で live_criteria を評価する」と明記する。
- (2) T037 並行投入: 可能。ただし Phase0 完了後にリベース測定を再実行し差異を評価すること、active-clause 集計は Stage C 開放後の挙動が本命と注記。
- (3) `max_spread_bps=10` 妥当性: EUR/JPY・USD/JPY では 8–12 bps が Tier1 想定、EUR/USD は 5–8 bps 程度。Phase0 は共通 10 bps、Phase1 で `per_pair` 設定と stress multiplier 1.5 を確認する。広いペア（GBP/JPY 等）は Phase2 以降に個別調整。
- (4) mission_score 数式案: 各軸 i に対し `score_i = clip((metric_i - lower_i) / (target_i - lower_i), 0, 1)`（lower_i は fail 閾値、target_i は live_criteria）。安全策として 0 を避けるため `score_i' = 0.1 + 0.9 × score_i` とし、`mission_score = (∏ score_i')^{1/4}` の幾何平均。下流で log 表示すれば距離感が分かりやすい。WinRate / TradeCount は非線形性を考慮し、必要なら logistic に差し替え。
- (5) RUN 凍結 / DoD: 凍結に同意。DoD 案: (a) `max_spread_bps` 実装＋StageC pass条件が code/test で確認済、(b) Sharpe 閾値換算 docs 更新＋replay グラフ添付、(c) T037 metric が report に反映され QA 済、(d) mission_score が archive/report に記録される。全項目満たすまで RUN 再開不可。
- (6) C roadmap 修正案: Phase0 の順番は P0-1 (spread) と P0-2 (閾値換算) を Day1-2、P0-3 (T037) と P0-4 (mission_score) を Day3-5 に並行配置。Phase1 で aux pipeline を実装する際、`strict_aux_required=False` だけでなく欠損 logging を structured データに残す追加要件を入れたい。

## 4. Codex 追加論点
- Stage C 開放後、`spread_stress_skipped` 以外の fail 理由が顕在化する可能性が高い。fail taxonomy を整理し、report で件数分布を可視化するタスクを Phase0 or Phase1 に追加したい。
- aux data パイプライン構築前に、pair-specific primitives の期待レンジと正規化方式（例: pivot→z-score）の設計レビューが必要。誤ったスケーリングで clause オーバーフィッティングが再発するリスクがある。
- trade-level Sharpe の再標準化では、`trade_count_min_for_sharpe` を 30 とするデフォルトが適切か再検証（小標本補正）すべき。n<30 のケースは C7 に抵触するので、閾値再設定時に `trade_count` フィルタの引き上げを検討。

## 5. Verdict
- Phase0 優先タスクと DoD:
  - ① `max_spread_bps` 導入＋StageC pass 単体テスト追加 (`tests/` or replay)／DoD: stress チェック通過個体を replay で確認。
  - ② Trade-level ⇄ annualized Sharpe 換算の実装＆docs 記載／DoD: Run14-16 再計算チャートと換算式明文化。
  - ③ T037 active-clause 伝搬＆StageA reason telemetry／DoD: report に metrics 表示、監査で検証。
  - ④ mission_score 算出＆archive/report 出力／DoD: sample run（過去 archive）に mission_score が追記される。
- 全体ステータス: 上記 DoD が満たされるまで RUN 17 凍結に合意。閾値換算式の最終値は経験分布分析待ちにつき「INCONCLUSIVE（数値確定待ち）」だが、手順と式の骨格は合意済み。