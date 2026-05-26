# 分析 (cycle 25): R105 INVALID 判明 — spawn worker registry 伝播バグ修正 → F15 再検証

## 結論 (先出し)
**R105 の「REJECTED」は無効**。F15 が効かなかったのではなく、**F15 が一度も評価されなかった**。
spawn worker の registry に F15 が伝播せず、F15 含み genome が全て Stage A で
`KeyError: primitive 'F15' not in registry` で全滅していた。バグ修正後 R106 として再検証する。

## 観察事実 (Facts)
- R105 (seed70, --enable-mtf-primitive ON) ログ:
  - main process: `run_ga.experimental_primitive.enabled kind=mtf_trend_pullback id=F15` ✅
  - 直後から: `stage_a.system_failure error="primitive 'F15' not in registry" KeyError genome=g0_i0 ...` 多発
- archive: F15/MTF を参照する genome は 129 行生成されたが、**stage_c_pass 795 個体中 F15 使用は 0**。
- R105 metrics ≈ R101 control (median pnl 84320 vs 82150、ann 5.47 vs 5.58、max 89510 vs 92360)
  = F15 genome 評価枠が無駄になった分だけ control 相当。

## 根本原因 (Root Cause)
`src/alpha_factory/parallel_eval.py`:
- GenomeEvaluator は `multiprocessing.get_context("spawn").Pool(initializer=_init_worker, ...)`。
- `_init_worker` は spawn worker で `ensure_registered()` のみ呼ぶ (registry 32 本)。
- main process で呼んだ `register_experimental()` (F15 追加) は **spawn worker に継承されない**。
- 一方 random generator は main process で動き F15 含み genome を生成 → worker へ送付 → worker
  registry に F15 が無く KeyError → Stage A 全滅。
- cycle24 impl-review が捕捉した「同一プロセス内 OFF run への F15 残留」(=`_clear_registry()` で対処)
  とは別の、**プロセス間伝播**の見落とし。

## 修正 (Fix, this cycle)
1. `_init_worker(..., enable_experimental: bool = False)`: True 時 `register_experimental()` を
   worker でも呼ぶ。default False で従来 bit-exact (32 本)。
2. `GenomeEvaluator.__init__(..., enable_experimental=False)`: Pool initargs に伝播。
3. `run_ga.py`: GenomeEvaluator に `enable_experimental=getattr(args,"enable_mtf_primitive",False)`。
4. 回帰テスト `TestInitWorkerExperimentalPropagation` (OFF=32/F15なし, ON=33/F15あり)。
   in-process 検証で OFF count=32/F15 False, ON count=33/F15 True を確認済。171 tests pass。

## bit-exact 不変性
- OFF (default、--enable-mtf-primitive 未指定): `enable_experimental=False` → worker は
  ensure_registered() のみ = 32 本。main process も register_experimental() 呼ばず。完全 bit-exact。
- ON 経路のみ挙動変化 (F15 が実際に評価されるようになる=本来の意図)。

## 次手 (Plan)
- R106 = F15 treatment 再実行 (seed70、修正後、--enable-mtf-primitive ON)、R101 control 反実仮想。
- 判定基準は cycle24 の Codex 5 条件をそのまま流用 (1つでも未達 REJECTED):
  1. mission_candidate ≥615  2. stage_c_pass ≥615
  3. pooled median ann sharpe ≥5.78 (+0.20)  4. pooled median total_pnl ≥87k (+5000)
  5. tail: p90(total_pnl) 改善 or max_pnl>108810。
- 今度は F15 が実際に genome に取り込まれ評価されるため、初めて F15 の表現力寄与を検証可能。
- 成功 → F15 採用候補、seed71 2seed 確認。REJECTED → F15 真に不採用 (opt-in 維持・bit-exact)、
  Codex 合議で別 primitive family (b 時間帯 / c vol regime / d 非線形トレンド) or 総括。
