# Conceptual Design R2 — run-ga-full-rewrite (T018)

R1 Codex レビュー (`conceptual-review-r1.md`) の指摘 6 件をすべて取り込んだ修正版。
本 R2 で固定した方針は `detailed-design.md` に移し、Codex 詳細レビューに進む。

## R1 指摘 → R2 対応マッピング

| # | R1 指摘 (要約) | R2 対応 |
| - | --- | --- |
| 1 | 単一 instrument で `pair_bars={X: bars_18m}` のみ注入すると、`evaluate_cross_pair` が target+anchor 2 本必須のため skipped のまま graduation が永久 0 件 | **cross-pair は明示的に disabled/monitor-only** とし、summary に `cross_pair_enabled: False` を出す。Phase 2 単一 instrument mode では target+anchor の 3 ペア全て bars を揃えたときのみ有効化。default config では 1 ペアのみなので shadow 評価は skipped 記録のみ、graduation 判定は **`require_cross_pair_pass` を single-instrument 時のみ自動 False にする** fallback を config に持たせる (新 flag `cross_pair_strict_for_graduation`)。multi-pair bars が渡されたときは従来通り shadow 動作。 |
| 2 | `effective_fitness = fitness_pen + 1000/10000/100000` を `best.fitness` に出すと analyze_run/generate_run_report が壊れる | **選択用 tuple key を別実装**し、外部出力は `fitness_pen` (Stage A の penalized sharpe) のみ。`best.fitness` / `history[*].best_fitness` は従来通り Decimal 文字列化された `fitness_pen`。追加情報として `best.stage_a_pass/stage_b_pass/stage_c_pass` と `best.selection_score` (lexicographic の可視化) を **追加キー** として summary に残す。 |
| 3 | `dataset.start/end` を「Stage B 期間」に意味変更すると既存 config/後方互換が崩れる | **`dataset.start/end` は従来意味 (対象期間) のまま保持**。追加で `stage_windows` セクションを新設し、`stage_a_window_days` / `stage_b_window_days_from_end` / `stage_c_holdout_days` を相対指定。Stage A/B/C の bars は `dataset.start/end` の範囲を分割する仕様 (default: Stage A/B は dataset 範囲、Stage C holdout は dataset.end 以降を fetch 試行、取れなければ fail-fast)。 |
| 4 | holdout fallback に Stage B 末尾 slice を使うと leakage | **production は fail-fast**。test fixture 専用の `allow_stage_c_fallback_slice` flag を config に持たせ、DEFAULT false。yaml コメントで警告、CLI には expose しない。 |
| 5 | `AlphaFactoryConfig.live_criteria` と `StageGateConfig.live_criteria` を二重保持すると drift | **StageGateConfig に一本化**。yaml top-level の `live_criteria` は loader 時に `StageGateConfig.live_criteria` に注入、`AlphaFactoryConfig` は alias property (`@property def live_criteria(self) -> Mapping`) として expose。 |
| 6 | LaneManager が parent_a/parent_b を受け取る経路無し、系譜情報が抜ける | **population entry を `list[GenomeEntry]` に拡張**。`GenomeEntry = dataclass(genome: Genome, parent_a: str | None, parent_b: str | None)` を run_ga.py 側で保持し、LaneManager には渡さず、run_ga.py が archive.collect_stage_a を呼ぶ前に provenance を直接 archive に pre-register する... という案は LaneManager 責務を壊すので不採用。代わりに、**Tier1Lane.population の要素を `Genome` のままとし、別途 `Tier1Lane.provenance: dict[str, tuple[str|None, str|None]]` を追加**し、`_run_tier1_generation` が `collect_stage_a` 呼び出し時に `parent_a=provenance.get(genome.name, (None, None))[0]` のように渡す。これは T017 実装への最小侵襲拡張。ただし、Codex R1 指摘 (LaneManager 自体の変更) はスコープが広いため、**R2 では代替案として run_ga.py が provenance を archive.collect_stage_a に直接書き込む経路は採らず、Tier1Lane に provenance dict を追加し LaneManager 側が参照する** (§4.2 参照)。 |
| 6b (追加) | summary.json の既存キー (`dataset.instrument`, `dataset.start/end/bars`) をサンプルから削っていた | **既存 top-level キーは完全維持**。新情報は `dataset.bars_stage_a/bars_stage_b/bars_holdout`、`per_generation`、`archive_parquet` など、**追加のみ**。`ga_config.fitness_metric` の意味は「Stage A の fitness_pen が算出するベース指標 = sharpe」で維持。 |

## 固定された設計原則 (R2)

1. **SSOT**: `live_criteria` は StageGateConfig のみ。`AlphaFactoryConfig.live_criteria` は alias property。
2. **dataclass loader 分離**: YAML → dataclass は `src/alpha_factory/config.py` の `load_config(path, overrides=None)` に閉じる。
3. **fitness 二層分離**: 外部出力 (`summary.best.fitness`, `history.*.best_fitness`) は `fitness_pen` のみ。内部選択 (tournament / elite) は `(stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` の tuple。
4. **cross-pair 契約の明示化**: 単一 instrument mode では cross-pair は skipped になることを summary に `cross_pair_mode = "skipped_single_instrument"` で明示。graduation 判定は `cross_pair_strict_for_graduation` で切替 (default False = 単一 instrument でも graduation 可能)。
5. **bars 3 区間分割**: `dataset.start/end` は従来意味。`stage_windows.stage_a_window_days` が Stage A bars の末尾営業日数、`stage_windows.stage_c_holdout_days` が `dataset.end` 以降の holdout、Stage B bars = dataset 全体。
6. **provenance 記録**: `Tier1Lane.provenance: dict[str, tuple[str|None, str|None]]` を追加し、LaneManager が `collect_stage_a` 呼び出し時に `parent_a/parent_b` を渡す。T017 実装の最小修正。
7. **summary.json 既存契約維持**: `dataset.instrument/start/end/bars` は維持、`best.fitness` は Decimal 文字列で維持、`history` 要素形式も維持。

## Non-goal 再確認

- Multi-instrument 並列実行 (swim-lane の真価) は別 TODO
- Graduation lane 実 GA (seed based GA) は別 TODO
- cross-pair hard gate 切替は Phase 4

## 判断確認項目 (R2 で固まったもの)

1. fitness の選択用 tuple (§3) — **採用**。
2. bars 3 区間分割 (§5) — **採用**。ただし Stage C holdout が取れないなら fail-fast。
3. `src/alpha_factory/config.py` 新設 (§1) — **採用**。既存 `StageGateConfig` / `CrossPairConfig` を再エクスポートし、`AlphaFactoryConfig` を追加するだけ。
4. LaneManager との責務分離 (§6) — **採用**。Tier1Lane に provenance dict を追加 (T017 micro-extension)。

## detailed-design.md へ委譲する項目

- `src/alpha_factory/config.py` の完全 dataclass 構造と loader 実装
- `run_ga.py` の関数シグネチャ・内部フロー・fitness 選択ロジック
- bars ロード手順 (Stage A/B/C の slicing)
- テスト設計 (4 テストケース)
- summary.json / history.json / best_genome.json の最終スキーマ

（詳細は同 dir `detailed-design.md` 参照）
