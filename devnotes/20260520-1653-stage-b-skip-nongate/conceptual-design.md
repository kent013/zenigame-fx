# 概念設計: Stage B 非ゲート observability の条件化 (wall-time 削減)

## 前提 (C4) — Round 1 で consumer inventory + 副作用検証を追加

| 項目 | 状態 | 根拠 |
|---|---|---|
| Stage B が CPU 時間の 83% (45,507s / 全 54,582s) | **verified** | Run 82 summary.json per_generation 集計 |
| Stage B wall ≈ 7.6h (15.2h CPU / 2 worker) | **verified (算術)** | 同上、 max_workers=2 |
| Stage B 合否は fold OOS 指標のみ (median_oos_sharpe + positive_fold_ratio + n_fold_effective、 profit_safe_pfr variant) | **verified** | stage_gate.py:1520-1591 の reasons 構築 |
| **Stage B の IS-monitor (242k full backtest) は hard gate に使わない** | **verified** | docstring stage_gate.py:1262「IS metrics は monitor として記録 (hard gate には使わない)」 |
| 実行順は IS-monitor (1313) → fold loop (1377) | **verified** | コード行順 |
| IS-monitor 242k > fold 合計 ~115k (8 fold × test ~14k) | **verified (概算)** | wf_test_days≈10 × 1440 × 8 fold |
| gen30 で A 通過 57 → B 通過 32 (= 25 が Stage B 失敗) | **verified** | run-82 summary per_generation gen30 |

### Consumer inventory: is_full_* / canonical_shadow_b_is の全消費経路 (Round 1 [Critical] C4/Q1)

| field | writer | reader | GA 決定に逆流? |
|---|---|---|---|
| is_full_sharpe / total_pnl / trade_count | stage_gate.py:1303-1324 (payload) | archive.py:686-702 (列 trade_sharpe_stage_b / trade_count_stage_b へ書込) | **No** |
| canonical_sidecar_b_is | stage_gate.py:1329 | archive.py:735 (canonical_shadow_b_is 列へ書込) | **No** (payload 非添付、 sidecar) |
| trade_sharpe_stage_b / trade_count_stage_b (archive 列) | archive.py | **offline 監査スクリプトのみ** (audit_run_post.py:75 / inspect_stage_b_folds.py:75 / analyze_stage_b_diagnostic.py) | **No** |

- grep 結果 (verified): `is_full_*` / `canonical_shadow_b_is` を読むのは archive writer
  + swim_lane の sentinel 設定経路 (swim_lane.py:540, = pre_flight_underfilled の
  None 埋め、 消費でない) のみ。 fitness / selection / Stage C promotion /
  cross-pair / report の **GA 決定経路は一切読まない**。
- `analyze_stage_b_diagnostic.py:179` 自身が「trade_sharpe_stage_b は判定 SSOT
  ではない、 median_oos_sharpe と混同禁止」と明記。

### 副作用検証 (Round 1 [Critical] リスク 1 / Q2)

| 副作用源 | 検証 | 結果 |
|---|---|---|
| RNG 消費 | engine.py / strategy.py / eval.py / mock.py を grep (random/rng/seed/shuffle) | **RNG 不使用** (verified) → IS-monitor 実行は乱数状態を変えない |
| global mutable state | _bars_cache (id(bars) keyed LRU) / _PROC_AUX_CACHE (id(aux_bundle) keyed) | **値は order 非依存** (cache は「何が載るか」を変えるだけで計算値は不変) |
| backtest の純粋性 | run_backtest は bars/strategy/broker/config のみ依存、 新規 broker/strategy を毎回生成 | **near-pure** (verified、 golden test で最終確認) |

### 最強の安全論拠 (Round 1 反映)
スキップは **fold-gate 失敗個体のみ**。 失敗個体は **Stage C 候補にならない**
(Stage C は Stage B passers のみ対象)。 よって Stage C promotion / cross-pair /
best 個体 tie-break が参照しうるデータは **passers のみ = IS-monitor を依然実行**
するため完全不変。 変わるのは **失敗個体の archive shadow 列 (offline 監査専用)**
のみ。

## 背景・課題

production GA Run は wall ~6-7.6h。 Stage B が CPU の 83% を占める。 Stage B は
Stage A 通過個体ごとに (gen30 で 57/96):
1. **フル IS-monitor backtest (242k bars, 非ゲート observability)**
2. **canonical_five 計算 (242k 相当, 非ゲート observability)**
3. 8 fold backtest (~115k bars 合計, **これが唯一の合否ゲート**)

最大コストの (1)+(2) は **GA 合否・fitness・選抜に一切影響しない observability
専用**。 archive shadow 列と log にのみ記録される。

zenigame (姉妹) は `stage_b_early_termination` (T506) + C-lite で「後工程ほど
個体/計算を絞る」設計。 zenigame-fx の Stage B はこの絞り込みが無く、 非ゲートの
242k×2 パスを **Stage B 失敗確定個体 (gen30 で 25/57) にも完走**している。

## 改善アイデア

**非ゲートの IS-monitor + canonical_five を、 fold gate 通過個体のみに限定する。**

- 実行順を変更: **fold loop (ゲート) を先に実行 → pass/fail 判定 → IS-monitor +
  canonical は (条件付きで) 後置き**。
- fold gate 失敗個体では IS-monitor + canonical を **スキップ**し、 IS 系 field は
  sentinel で記録。 **既存 except sentinel とは区別**するため、 新たに
  `b_is_shadow_status: "computed" | "skipped_fold_gate_fail" | "error"` を
  payload/archive に持たせ、 「設計上スキップ」と「計算失敗」を分離
  (Round 1 [Critical] Q3 反映、 監査性維持)。
- GA の合否は fold 指標のみ依存 (verified) なので、 **選抜・fitness・best 個体は
  完全不変**。 削減されるのは失敗個体の非ゲート 242k×2 パスのみ。

「機能の名前に立ち返れ」: IS-monitor は名前通り monitor (観測)。 ゲートではない。
観測を「ゲート通過個体のみ」に絞るのは monitor の役割と矛盾しない (失敗個体の
詳細観測は監査上の価値が低い)。

## 期待効果 (仮説)

- H1 (**仮説レンジ**, Round 1 [Warning] 4): Stage B wall-time 削減。 削減幅は
  「bar 数比例 = 時間比例」を仮定した概算で **中心 10-20%、 レンジ 0-25%**
  (全体 wall 基準)。 bar 数比例の仮定自体が未検証のため、 **IS-monitor / canonical
  / fold の Stage B 内時間内訳を先に実測**して根拠を固める。 正確な削減は
  stage_b_seconds_total の before/after で確定。
- H2 (絶対要件): GA 結果 (合否 vector・fitness ranking・選抜・best 個体・
  archive **gate 列**・Stage C candidate set) が baseline と **完全不変**。
- H3: 既存テスト全 pass。 peak RSS / per-worker RSS が **悪化しない**
  (Round 1 [Warning] 7、 順序変更でオブジェクト寿命が変わるため計測)。

### 成果判定 / REJECT 条件 (Round 1 [Critical] Falsification 反映)

合格条件: 下記 reject 条件に該当せず、 かつ Stage B wall-time 削減 (実測 >0)。

**REJECT 条件 (1 件でも該当で即 reject)**:
- 同 seed で **Stage B pass/fail vector** が 1 件でも変わる
- **fitness ranking** が 1 件でも変わる
- **Stage C candidate set** が変わる
- **archive gate 列** (fold 指標・pass フラグ) が変わる
- 非ゲート shadow 列以外に差分が出る
- 既存テスト fail / peak RSS 悪化

許容差分: **非ゲート shadow 列 (trade_sharpe_stage_b / trade_count_stage_b /
canonical_shadow_b_is) が、 fold-gate 失敗個体でのみ `skipped_fold_gate_fail`
sentinel になること** のみ。

## 効果の限界 (Falsification)

1. **IS-monitor+canonical が Stage B コストの小割合だった場合**: 削減幅が小さい。
   実測 (stage_b_seconds の IS vs fold 内訳) で確認。 → 内訳計測を先行 or 同時に。
2. **fold-gate 通過率が高い (失敗個体が少ない) 世代**: 後段世代ほど通過率上昇
   (gen60 で 49 通過/19 B pass = 30 失敗) → むしろ削減余地大。 ただし通過個体
   では IS-monitor を依然実行するため削減はゼロ。
3. **archive shadow 列の欠落が監査要件を破る場合**: 失敗個体の canonical_shadow_b_is
   等が sentinel になる。 監査が「失敗個体の IS shadow」を必要とするなら不可。

## 制約・前提

### 使命との整合
- live_criteria 直接寄与なし。 探索の wall-time 短縮 = **同じ時間で多く Run
  でき探索を加速** (間接的に使命達成を早める)。
- **GA 結果不変が絶対**。 strategy quality は変えない。

### 正確性 (絶対)
- Stage B gate = fold OOS 指標のみ (verified)。 IS-monitor/canonical は非ゲート。
  よって本変更は **GA 選抜・fitness を構造的に変えない**。 golden test で
  「同 seed の best 個体・合否・fitness が baseline 一致」を検証。
- archive の **gate 関連列は不変**。 非ゲート shadow 列 (canonical_shadow_b_is,
  is_full_sharpe 等) のみ、 失敗個体で sentinel になりうる。

### 既存アーキ
- 順序変更のみ。 fold loop / gate 判定ロジックは不変。
- IS-monitor の except 経路 (既存) と同じ sentinel 値を流用 (新規 sentinel 不要)。

## スコープ外
- Stage A / Stage C
- fold 数・閾値・期間変更 (禁止事項)
- mmap SharedBarStore 移植 (別施策、 RSS/起動、 wall 非主因)
- scaled-int (B-1 で不要と判定済)
- C-lite 新設 (zenigame 先例だが本施策は Stage B 内に限定)

## 検証計画
- **内訳計測 (先行)**: Stage B 内の IS-monitor / canonical / fold の時間割合を
  簡易計測 (perf_counter) で確認 — H1 削減幅の根拠固め (Round 1 [Warning] 4)
- **golden (絶対)**: 同 seed (9999) smoke で best 個体 g2_i2 / fitness
  -0.02894014223533147 / 各 generation の A/B pass count・pass/fail vector が
  baseline 完全一致。 archive の gate 列が一致 (shadow 列のみ差分許容)
- wall: smoke の stage_b_seconds_total を before/after 比較
- RSS: peak_total / per-worker が悪化しないこと (順序変更の影響、 Round 1 [Warning] 7)
- 既存テスト全 pass (特に test_stage_gate.py の Stage B 系)

## 設計契約参照 (C1, Round 1 [Warning] 9)
- docs/alpha_factory/stage-gates.md (Stage B gate 契約)
- archive schema 契約 (GENOMES_SCHEMA, trade_sharpe_stage_b 等の列定義)
- run report 契約 (stage_b_seconds_total, A/B pass count)
を詳細設計で参照し、 gate 列 / shadow 列の区別を確定する。

---

## 結論 (Codex Round 2 後): 本設計は BLOCKED → max_workers 増に方針転換

### Stage B skip がブロックされた理由 (Codex Round 2 [Critical] 実証)
`is_full_trade_count` → archive `trade_count_full_dataset` (Stage A + Stage B
unique trade 数) → run_ga.py:938-948 `_update_cache` → `trade_count_for_feasibility`
→ `feasible` / `violation_magnitude` → `selection_score` 最上位キー
(run_ga.py:216-220)。 fold-gate 失敗個体も親選抜・best fallback 候補のため、
IS-monitor をスキップすると feasibility が変わり **GA selection が変わる = 結果が
変わる**。 フル IS backtest は feasibility のためスキップ不可。 skippable は
canonical_five のみ (Stage B コストの小割合) で、 費用対効果が低い。

### 真因と正しい解
- 計測 (B-1 findings + 本調査): メモリ問題は T106/T107 で解決済 (worker 9.5GB
  → 2.5GB、 total 23.7GB → 5.8GB)。
- 環境実測: **64GB RAM / 12 physical cores** (skill template の 24GB/6worker は
  誤り)。
- L1/L2 決定論は **worker 数に依存しない契約** (config:62, parallel_eval.py:11)。
- → **max_workers を 2 から増やす (例 8) のが、 GA 結果完全不変・config 変更のみ・
  低リスクで wall を ~4× 短縮する正しい解**。 Stage B の構造的計算量 (feasibility
  用 IS backtest + gate 用 fold) は削れないが、 並列度を上げれば wall は下がる。
- config の max_workers コメント (per-worker RSS 数GB) は T107 前の陳腐化情報。

本設計 (Stage B skip) は **Obsoleted**。 後続は max_workers 増の別 devnote で扱う。
