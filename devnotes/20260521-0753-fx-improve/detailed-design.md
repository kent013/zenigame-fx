# 詳細設計: Run 86 施策 (T101 warmstart adaptation, cycle 4)

## 使命・制約
live_criteria 全達成個体を seed 非依存に得る (再現性)。warmstart は初期集団への既知良個体注入 = 探索の足場で、評価関数・閾値・selection・GA dynamics は不変。default OFF で挙動完全不変。

## 既存インフラ整合 (調査結果)
- `loop_closure.py` / `cpps_archive.py` の warmstart (T066/T067) は **Phase 2 統合 (T102, 未配線・大規模) の一部**。実 GA run loop (run_ga.py:2077 は plain random_genome) には未配線。CPPS 配線 = T102 で cycle 1 Codex REJECT 済 (大規模・loop停止リスク)。
- → **T101 の simple initialize_population 注入を採用** (CPPS 機構と独立、低リスク)。既存 CPPS warmstart は触らない。

## 施策 T101: warmstart pool injection (default OFF)

### target_metric / failure_mode / causal_path / falsification / success_criterion
- target_metric: mission 個体の seed 非依存再現 (seed 67/68/69 各 run で live all_pass>=1)。
- failure_mode: mission 達成が seed-locked (seed68→43, seed67/69→0)。GA 探索軌道が seed 依存で profitable region 到達が不安定。
- causal_path: 既知 mission/Stage-C 個体を初期集団に注入 → gen 0 から評価・選択対象 → seed に依らず profitable region の足場が存在 → mission 個体が保持/再発見される。
- falsification: warmstart 適用後も seed 67/69 で live all_pass=0 のまま (注入個体が選択で淘汰される or 評価不能)。
- success_criterion: R86 (seed=67, 69) で各 live all_pass>=1。

### 変更箇所
1. **`src/alpha_factory/warmstart.py` (新規)**:
   - `load_warmstart_motifs(archive_path: Path) -> list[Genome]`: archive Parquet から `stage_c_pass==True AND total_pnl>=20000` の行の `genome_json` を抽出し `genome_from_dict` (src/dsl/serialize.py) で Genome 復元。**mission_score (or fitness_pen) 降順 sort** して返す (アンカー = motifs[0] が最良个体)。空/不在/読込失敗時は `[]` 返し fail-soft。
   - 上限 (例 max_motifs=64) で過大注入を防ぐ。
2. **`src/alpha_factory/config.py` GAConfig (131)**:
   - `warmstart_ratio: float = 0.0` (default 0.0 = 完全不変), `warmstart_motif_archive: str | None = None`。
   - `__post_init__` で `0.0 <= warmstart_ratio <= 1.0` 検証。
   - yaml loader (config.py:515 付近) に `warmstart_ratio` / `warmstart_motif_archive` 読込追加。
3. **`scripts/alpha_factory/run_ga.py` gen 0 初期集団 (2077)**:
   ```python
   if gen == 0:
       n_ws = int(cfg.ga.population_size * cfg.ga.warmstart_ratio)
       ws_genomes = []
       if n_ws > 0 and cfg.ga.warmstart_motif_archive:
           motifs = load_warmstart_motifs(Path(cfg.ga.warmstart_motif_archive))  # list[Genome]
           for i in range(n_ws):
               if not motifs: break
               # Codex Suggestion: i==0 は非 mutate アンカー複製 (既知 mission 個体を厳密保持)、
               # 残りは mutate で多様性 (Codex Warning: 単一固定回避)。
               if i == 0:
                   src_g = motifs[0]  # 最高 mission_score motif (load 側で降順 sort)
                   cand = src_g
               else:
                   src_g = motifs[rng.randrange(len(motifs))]
                   # ★ mutate 完全シグネチャ (operators.py:507): mutate(genome, rng, mutation_rate, *, max_clause, max_depth, registry)
                   cand = mutate(src_g, rng, cfg.ga.mutation_rate,
                                 max_clause=cfg.ga.max_clause, max_depth=cfg.ga.max_depth, registry=rg_registry)
               # ★ Critical 修正: genome_from_dict は元 name を復元するため replace で改名 + units 統一
               ws_genomes.append(replace(cand, name=f"g0_ws{i}", units=cfg.backtest.units))
       n_rand = cfg.ga.population_size - len(ws_genomes)
       rand_genomes = [random_genome(rng, name=f"g0_i{i}", units=cfg.backtest.units,
                       max_clause=cfg.ga.max_clause, max_depth=cfg.ga.max_depth, registry=rg_registry)
                       for i in range(n_rand)]
       population = ws_genomes + rand_genomes
       provenance = {g.name: (None, None) for g in population}  # g0_ws* も登録、名前衝突なし
   ```
   - **default warmstart_ratio=0.0 → n_ws=0 → ws_genomes=[] → n_rand=population_size → population は現行と完全同一 (random_genome のみ、name=g0_i*、rng 消費順も不変)**。これが数値同一性の絶対条件。
   - **Critical 修正 (Codex R1)**: `mutate(genome, rng)` は name 引数を取らない (src/ga/operators.py:507)。`genome_from_dict`/serialize は archive の元 name を復元するため、注入個体は必ず `replace(g, name=f"g0_ws{i}", units=cfg.backtest.units)` で改名 (g0_ws* で g0_i* と衝突しない)。
   - mutate は既存 breeding mutation (src/ga/operators.py) を流用。
   - import: `from dataclasses import replace`, `from src.dsl.serialize import genome_from_dict` (warmstart.py 内)。
4. **CLI** (run_ga.py argparse): `--warmstart-ratio` / `--warmstart-motif-archive` 追加 + cfg.ga へ反映。
5. **波及**: AGENTS.md / SKILL.md に新 CLI オプション記載 (run-alpha-factory が passthrough)。

### default 不変の保証 (最重要)
- warmstart_ratio=0.0 (default) で n_ws=0 → ws_genomes 空 → population = 現行と同じ random_genome 列 (同 rng・同順)。既存全テスト pass が条件。
- rng 消費: warmstart 経路は `n_ws>0` のときのみ rng を消費。n_ws=0 で rng 状態は現行と完全一致。

### テスト計画
- [ ] load_warmstart_motifs unit: R85 archive (.cache/alpha_factory/runs/genomes_run_20260520_202321.parquet) から motif 抽出、stage_c_pass&pnl>=20000 のみ、mission_score 降順、空/不在 archive で [] (fail-soft)。
- [ ] GAConfig warmstart_ratio 検証 (範囲外 raise)、default 0.0 / warmstart_motif_archive default None。
- [ ] ★ **invariance (Codex Warning)**: warmstart_ratio=0.0 で load_warmstart_motifs/mutate が呼ばれないこと (mock/spy)、かつ同 seed で gen0 genome 列 (name=g0_i*) が baseline と完全一致。
- [ ] warmstart_ratio=0.1 で初期集団に g0_ws* が int(pop*0.1) 個含まれ、ws0 はアンカー (motifs[0] の非 mutate 複製、name のみ改名)、ws1+ は mutate 派生。
- [ ] genome_from_dict 復元 + replace(name,units) の健全性 (注入個体が有効な Genome、name 衝突なし)。
- [ ] 既存 run_ga / config テスト全 pass (default 不変)。

### リスク
- 低-中。default OFF で挙動不変。リスクは rng 消費順の混入 (n_ws=0 で経路に入らないことをテストで保証)。mutate 関数の流用ミス。
- 注入個体が即淘汰される可能性は受入基準 (R86) で検証 (falsification)。

## Run 86 実行パラメータ (warmstart 検証)
| パラメータ | 値 |
|-----------|-----|
| instrument | EUR_JPY |
| population-size | 96 |
| generations | 60 |
| mutation-rate | 0.5 |
| max-workers | 2 |
| stage-b-gate-kind | profit_safe_pfr |
| **warmstart-ratio** | **0.1** |
| **warmstart-motif-archive** | **.cache/alpha_factory/runs/genomes_run_20260520_202321.parquet** (R85) |
| seed | **67 と 69 を各 run** (R84/R82 で mission=0 だった seed で再現性検証) |

> R86 は seed=67, seed=69 の 2 run。warmstart で各 run live all_pass>=1 なら受入基準達成 (mission seed 非依存化)。最初に seed=69 を実行 (R84 で mission=0 の seed)。

### 成功基準の明示 (Codex Suggestion)
本施策は **再現性検証 (reproducibility)** であり、**汎化性能検証 (generalization) ではない**。R85→R86 は同一 dataset/holdout を使うため、warmstart で mission 個体が seed 非依存に保持/再発見されることを示すのが目的。別 dataset/別期間での汎化は別レーン (Alpha Sieve OOS / cross-pair gate P3) の課題。

## Codex design-review: REQUEST_CHANGES → 修正反映済 (Round 2 で確認予定)
Round 1 [Critical] (mutate signature: name 引数なし → replace で改名 + units) 反映。[Warning] (ratio=0.0 invariance テスト) 反映。[Suggestion] (i==0 非 mutate アンカー / 再現性≠汎化 明記) 反映。
