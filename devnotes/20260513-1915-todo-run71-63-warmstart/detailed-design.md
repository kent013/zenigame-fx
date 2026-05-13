# Run 71/63 warmstart 詳細設計

## 実装方針

### candidate motif 抽出

archive Parquet (= 58 列) から:
- `stage_c_pass=True` AND `total_pnl >= 20000` の個体集合
- 各個体の `genome_json` を取得
- 同 cluster (= primitive set Jaccard >= 0.7) を merge し motif として登録

### warmstart 注入

GA `initialize_population()` 修正:
```python
warmstart_ratio = ga_config.warmstart_ratio  # default 0.0 = 完全行動不変
n_warmstart = int(population_size * warmstart_ratio)
if n_warmstart > 0:
    motifs = load_warmstart_motifs(archive_dir)
    for i in range(n_warmstart):
        seed_genome = random.choice(motifs)
        # mutation で派生
        warmstart_genome = mutate(seed_genome, mutation_rate)
        population.append(warmstart_genome)
n_random = population_size - n_warmstart
population.extend([random_genome() for _ in range(n_random)])
```

### config

```python
class GAConfig:
    warmstart_ratio: float = 0.0  # default 0 = 完全行動不変
    warmstart_motif_archive: Path | None = None  # archive Parquet path
```

### CLI

```bash
--warmstart-ratio 0.1
```

## 受入基準

- [ ] warmstart.py 新規 + motif 抽出 + mutation
- [ ] GAConfig 拡張 + 4 段接続
- [ ] default 0.0 = 完全行動不変 (= 既存 test 全 pass)
- [ ] PR tests (= motif 抽出 unit test + initialization integration test)

## smoke 合格条件

- warmstart_ratio=0 で baseline 完全一致
- warmstart_ratio=0.1 で初期 population に Run 71/63 motif 系統が 10% 含まれる
- Run 71/63 系統由来個体の Stage C 通過率 ≥ baseline

## コミット計画

- 1 コミット: `feat(ga): warmstart pool (Run 71/63 motif 再現性検証、 default OFF)`
