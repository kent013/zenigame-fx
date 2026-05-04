# 最終改善計画: Run 27 → Run 28

**作成日時**: 2026-05-04 12:55 JST
**合議ステータス**: **CONSENSUS REACHED (Round 2)**
**前提**: analysis-merged.md / consensus-round-1.md / consensus-round-2.md
**北極星**: live_criteria 充足 FX イントラデイ戦略個体を 1 つ見つけ出す
**現在地**: trade_sharpe_raw max ≈ 0.001 / live_criteria.sharpe_min=1.0 (annualized) → **要改善幅 ~1000 倍**

## エグゼクティブサマリー

Run-27 集団全壊滅 (Stage A pass=0) に対し、 **Phase C 着手前に C1 Design-first で grep + Read を実行** した結果、 Round 1 の P1/P2 監査仮説が **即時反証**:

- 反証 1: Stage A 判定式は **設計通り** (`fitness_pen = sharpe - alpha * size_norm` で run-27 best 検算合致、 [stage_gate.py:837-839](src/alpha_factory/stage_gate.py#L837-L839))
- 反証 2: archive 列 archive_role / source_stage = NaN は **設計上ハードコード None** (`archive.py:179-180` + コメント明示、 上流 T066/T063-T064 main flow 統合待ち = handoff § 6.5.2 dormant chain と整合)

= 「Stage A pass=0 = 判定 bug」 仮説は **棄却**、 真の root cause は **戦略性能不足側** (= primitive / 探索 dynamics / penalty 設計のいずれか)。

Round 2 で Codex と合意 (= APPROVED):
- Run-28 = **(c) diagnostic instrumentation のみ** = 「成果改善ではなく North Star に向けた誤った次手を防ぐ診断 Run」
- GA 設定 **完全不変** (max_clause=1 / pop=40 / gen=15 等)
- Run-29 の打ち手を 1 つに分類できる状態を作る

## 反証可能仮説 (= 唯一)

> Stage A pass=0 の root cause は (P1) **primitive 表現力不足** (= raw signal そのものが弱い)、 (P2) **penalty / config 設計** (= raw はあるが size_norm penalty で潰される)、 (P3) **探索 dynamics** (= elite による短い genome 集約で diversity 崩壊) のいずれかである。 Run-28 diagnostic で 1 つに分類できる。

### 分類条件 (= Codex Round 2 承認)

| 観察 | 仮説 | Run-29 打ち手候補 |
|---|---|---|
| trade_sharpe_raw が全世代で天井 (= max << 1.0 で動かず) | **(P1) primitive 表現力不足** | post-run-review 担当 (= 当 cycle 範囲外、 中期キュー) |
| trade_sharpe_raw あるが fitness_pen で落ちる (= raw > 0 個体が複数あるのに penalty で fail) | **(P2) penalty / config 設計** | alpha (0.03) or threshold (0.0) 調整 = Principled Parametric (= 構造的に「短 genome 優位なのに penalty で殺している」 場合) |
| n_nodes / active_clause が generation で単調減少、 diversity 崩壊 | **(P3) 探索 dynamics** | mutation_rate 調整 / elite_count 削減 / max_clause 1→2 (= 表現力拡張で diversity 維持) = Structural |

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | **Stage A root cause diagnostic 集計 script** | 既存 archive Parquet (`.cache/alpha_factory/runs/genomes_{run_id}.parquet`) を入力に: (a) fitness_pen 分解 (raw / size_norm 寄与) (b) trade_sharpe_raw 分布 (世代別 / trade_count バケット別) (c) size_norm × trade_sharpe_raw 散布 (d) n_nodes / active_clause 世代推移 (e) 失敗理由別件数 (NO_EXPOSURE / metric_unavailable / below_threshold / system_failure) (f) 上記から (P1)/(P2)/(P3) 分類判定 を出力 | 新規 `scripts/alpha_factory/analyze_stage_a_diagnostic.py` + テスト | **Critical** | **Structural** (= 新規 diagnostic script、 既存コード不変) | (前段) Run-29 の打ち手を 1 つに分類できる状態の確立 | Stage A pass=0 の root cause が (P1)/(P2)/(P3) のどれか不明 | 既存 archive parquet の集計から仮説を 1 つに絞れる | 集計 script の出力で root cause が 1 仮説に分類される | (a) `reports/run-{N}/diagnostics/stage_a_root_cause.md` 生成 (b) 上記分類条件のいずれか 1 つに分類できる (c) 適用は Run-27 (既存) + Run-28 (新規再走、 結果安定性確認) の 2 RUN で実施 | **APPROVED** Codex Round 2 |

## 却下された提案 (Codex Round 2 で正式 REJECT)

| # | 提案 | 却下理由 |
|---|---|---|
| P1 (Round 1) | Stage A 判定契約監査 + archive 一致監査 | grep + Read で既に反証済み (= 設計通り正常動作)、 監査価値なし |
| P3 | max_clause 1→2 AB 前倒し | Run-28 で実施するには root cause 未分解、 1 RUN では因果読めない (= max_clause=2 は表現力 / size penalty / 探索空間 / 過剰取引構造を同時に変える)。 Run-28 diagnostic 後に 仮説 (P3 探索 dynamics) が支持された場合のみ Run-29 候補 |
| P4 | cross-pair 多通貨拡張 | Stage A 全滅では一次ボトルネックではない、 中期キュー据え置き |

## 保留事項

| # | 仮説 | 最小変更案 | 検証条件 |
|---|---|---|---|
| H1 | Run-28 diagnostic 結果次第で Run-29 打ち手決定 | 上記分類条件の Run-29 打ち手候補のいずれか 1 つ | diagnostic 出力で root cause が 1 仮説に分類される |
| H2 | dual-path 副作用 (= I6) | INCONCLUSIVE (C8)、 別 cycle で legacy ON/OFF replay 比較 | 同一入力で stage 判定・fitness 差を比較 |
| H3 | cross-pair multi-instrument 拡張 | swim_lane.tier1 6 ペア展開 + cross_pair anchor 検証 | tier1 全ペアで lane 確立後、 cross_pair shadow emit |
| H4 | primitive 表現力改革 (= P1 仮説の打ち手) | post-run-review 担当 (= 当 cycle 範囲外) | Run-28 diagnostic で (P1) primitive 不足が支持された場合 |

## メタ過学習ガード適合性

| 項目 | 評価 |
|---|---|
| C1 (Structural、 既存 archive 集計の新規 script) | OK = 数値弄りなし、 GA 挙動完全不変 |
| 取引回数削減で見かけ向上 (#6) | N/A |
| 期間延長で過学習隠蔽 (#1) | N/A |
| live_criteria 緩和でステージ skip (#4) | N/A |
| 見栄え改善 (#2) | N/A |
| オーバーナイト前提 (#7) | N/A |
| archive スキーマ伝搬漏れ (#8) | **C1 で逆に検証** (= NaN 列の設計的根拠を grep で確認、 #8 違反でないことを documented) |
| やたらに複雑な案 (#5) | **新規 script 1 個のみ、 既存コード touch なし** = 最小変更原則準拠 |

## 次フェーズへの申し送り

### Phase C (詳細設計) で確定すべき項目

1. **diagnostic script の入出力 spec**
   - 入力: `--run-id {run_id}` (= archive Parquet path 自動解決)
   - 出力: `reports/run-{N}/diagnostics/stage_a_root_cause.{md,json}`
2. **集計 metric の確定**
   - fitness_pen 分解 (raw - alpha * size_norm の 3 項分離)
   - trade_sharpe_raw distribution by generation × trade_count bucket
   - size_norm × trade_sharpe_raw 散布 (= penalty 効果の可視化)
   - n_nodes / active_clause 世代推移 (= elite による diversity 崩壊監視)
   - 失敗理由別件数 (Stage A reasons から)
3. **分類判定ロジック** (= P1/P2/P3 のどれかを script が自動判定)
4. **テスト計画**
   - 単体 test (= 既存 archive parquet を fixture として root cause 分類)
5. **波及変更**
   - `AGENTS.md` / skill 更新は **不要** (= 完全独立 script)
   - `docs/alpha_factory/` への運用記載は別 TODO で十分

### Run-28 実行パラメータ

| パラメータ | 値 | R-27 からの変更 |
|---|---|---|
| population_size | 40 | **不変** |
| generations | 15 | **不変** |
| max_clause | 1 | **不変** |
| max_depth | 4 | **不変** |
| max_workers | 2 | **不変** |
| stage_a.threshold | 0.0 | **不変** |
| stage_a.alpha | 0.03 | **不変** |
| その他 default.yaml | **完全不変** | — |

= **GA 設定は完全不変**。 Run-28 の目的は (a) 結果安定性確認 (Run-27 と同 setting で同 root cause 観察か) (b) diagnostic script を Run-27 + Run-28 両方に適用して分類確定。

### Run-29 以降の予告 (= Codex Round 2 推奨)

Run-28 diagnostic 出力に基づき:
- **(P1) primitive 表現力不足** が支持 → primitive 改革は post-run-review 担当 (= 当 cycle 範囲外)、 中期キュー
- **(P2) penalty / config 設計** が支持 → alpha (0.03) or threshold (0.0) を Principled Parametric として 1 軸調整
- **(P3) 探索 dynamics** が支持 → max_clause 1→2 (= 表現力拡張) or mutation_rate 調整、 same seed AB
