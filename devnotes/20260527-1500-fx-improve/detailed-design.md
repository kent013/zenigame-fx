# 技術設計 (cycle 26): anti-overfit 選択圧 `--robust-selection` (opt-in)

## 目的
Codex 合議(D)。失敗様式「A/B 適合過多が holdout に非汎化」を、新 primitive ではなく
**fold-CV 安定性を連続値 selection key に織り込む**ことで直接抑制する。holdout 情報は一切不使用
(リーク回避)。default OFF で完全 bit-exact、ON 時のみ選択順序が変わる。

## 北極星整合
anti-overfit 圧で pnl74k in-loop 崩壊 (R97: stage_c=0) を回避できれば、pnl 閾値の真の引き上げが可能。
取引数操作・期間延長・overnight 保有・holdout 利用は一切しない。

## robust_score 定義 (連続値, [0,1] 正規化)
既存 fold 統計 + 新規 OOS pnl 分散から構成。holdout 不使用。

```
robust_score = clip( w_pfre * positive_fold_ratio_effective
                   + w_sign * (1 - fold_sign_ratio)
                   + w_disp * (1 - normalized_oos_pnl_iqr), 0, 1 )
```
- `positive_fold_ratio_effective` (既存 archive 列): fold の正 sharpe 比率 (高=一貫)。
- `fold_sign_ratio` (既存 archive 列): 符号反転比率 (低=方向安定) → (1 - ratio) で高=良。
- `normalized_oos_pnl_iqr` (新規): per-fold OOS pnl の IQR を median_oos_total_pnl の絶対値+ε で
  正規化した変動係数的指標 (低=magnitude 安定) → (1 - x) で高=良。clip [0,1]。
- 重み初期値: w_pfre=0.4, w_sign=0.3, w_disp=0.3 (合計1)。CLI/config で調整可、default はこの値。

選択キーは `_selection_key` で fold_robust(index8) と fitness_pen(index9) の間に robust_score を挿入
(cross_pair_margin と同じ挿入様式)。cross_pair pressure と併用時は
`(*score[:9], robust_score, cp_val, score[9])` の順 (robust を cp より上位)。

## 実装変更点 (最小・加算的)
### 1. archive schema (`src/alpha_factory/archive.py`)
- 新規列 `oos_total_pnl_iqr: float` (default NaN) を追加。schema_version を +1 (現行から bump)。
- 後方互換: 既存 parquet 読込時に欠損列は NaN 埋め (pandas concat で自動、明示 default 設定)。

### 2. Stage B 集計 (`src/alpha_factory/stage_gate.py` ~1564-1601)
- `oos_total_pnls` list は既に存在。`oos_total_pnl_iqr = np.subtract(*np.percentile(oos_total_pnls,[75,25]))`
  を計算 (n_fold>=2 のとき、未満は NaN)。payload と archive row に格納。
- **bit-exact 保証**: この計算は観測値の追加のみ。Stage B pass/fail 判定・GA RNG・選択順序
  (OFF 時) に一切影響しない。

### 3. config (`src/alpha_factory/config.py`)
- `GAConfig` に `robust_selection_enabled: bool = False`、`robust_w_pfre/w_sign/w_disp: float` 追加。
  raw.get(..., default) で後方互換。

### 4. CLI + 配線 (`scripts/alpha_factory/run_ga.py`)
- `--robust-selection` (action store_true, default False)、`--robust-w-pfre/--robust-w-sign/--robust-w-disp`
  (default 0.4/0.3/0.3) を `--cross-pair-selection-pressure` 近傍に追加。
- config へ map。`_resolve_robust_selection()` SSOT 関数 (config + 前提チェック)。
- `IndividualCacheEntry` に `robust_score: float` フィールド追加。`_update_cache` で archive 列
  (positive_fold_ratio_effective, fold_sign_ratio, oos_total_pnl_iqr, median_oos_total_pnl) から計算。
- `_selection_key` に robust_score 挿入 (enabled 時のみ)。`_breed_next_gen` に param 配線。

### 5. bit-exact 不変性 (最重要)
- OFF (default): robust_selection_enabled=False → `_selection_key` は robust_score を挿入しない
  → 選択キー従来通り。archive に新列が増えるが GA の RNG・個体評価・選択順序は不変。
- 検証: 既存 GA 決定論テスト + 新規「OFF 時 selection_score tuple が従来 shape/値」テスト。
- ON 経路のみ挙動変化 (意図通り)。

### 6. テスト
- `oos_total_pnl_iqr` 計算 (n_fold>=2 で正, <2 で NaN, 既知配列で値一致)。
- robust_score 計算 (既知 archive row → 期待値、clip 境界)。
- `_selection_key` OFF=従来 tuple / ON=robust 挿入位置正しい。
- archive schema 後方互換 (旧 parquet 読込で欠損列 NaN)。
- 既存 171 + α、全 pass。

## R107 実験計画 (反証可能, in-loop counterfactual)
- R107a: `--robust-selection` ON, pnl70k (現行 frontier), seed70。control=R101。
  - Gate1 非退行: stage_c_pass≥650 かつ median ann≥5.4。
- R107b: `--robust-selection` ON, **pnl74k** (in-loop 引き上げ), seed70。
  - Gate2 崩壊耐性: stage_c_pass>0 (R97 型全滅回避)。
- 成功なら seed71 で再現 (Gate3): 2seed 中 1 以上で Gate2 達成。
- post-hoc sweep 禁止 (74k 教訓): 必ず in-loop full run で検証。
- 失敗 (Gate1 退行 or Gate2=0 を 2seed とも) → robust-selection 軸棄却、Codex 再合議。

## リスク
- nsga2 と同様 median 退行の懸念 → Gate1 で監視。robust_score は連続 tie-break (lexicographic 下位、
  feasibility/stage 通過の後) なので、生存集合は変えず順序のみ変える設計。崩壊回避が主目的。
- schema bump の後方互換 → 欠損列 NaN 埋めテストで担保。
