**前提（C4/C6）**
- 事実: 提示された `git diff` とテスト結果のみを根拠にレビューしました（コマンド実行なし）。
- 解釈: 設計整合は、差分中コメントと実装挙動の一致で判定しています（設計書本文の逐語照合は未実施）。

**[Critical]**
- 該当なし。

**ファイル別判定**

- [scripts/alpha_factory/run_ga.py](scripts/alpha_factory/run_ga.py): **[Warning]**
  - `summary["stage_b"]["n_fold_effective"]` 生成時に `int(best_row.get("n_fold_effective"))` を直接実行しており、将来 `NaN`/非整数混入時は `ValueError` でレポート生成が落ちる余地があります。`is_stage_b_inconclusive()` は防御的なのに、ここだけ型防御が弱いです。

- [scripts/alpha_factory/generate_run_report.py](scripts/alpha_factory/generate_run_report.py): **[Warning]**
  - コメントは「summary が無ければ archive から再導出」と書いていますが、実装は `None` のままスキップです。挙動自体は安全ですが、仕様説明と実装が不一致です（将来の誤読源）。

- [src/alpha_factory/stage_partition_guard.py](src/alpha_factory/stage_partition_guard.py): **[Suggestion]**
  - B-1 cond.4-6（集合重複）は現在の cond.1-3（厳密時系列）より実質冗長です。設計意図（将来の確率化対応）は妥当なので、コメントで「現行では冗長、将来有効化予定」をもう一段明示すると保守性が上がります。

- [tests/alpha_factory/test_stage_partition_guard.py](tests/alpha_factory/test_stage_partition_guard.py): **[Warning]**
  - cond.4-6 は「現順序だと単独発火が難しい」ことをテスト内コメントで認めており、実質的に直接検証できていません。将来 guard 順序を変えた際の退行検知力が弱いです。

- [src/alpha_factory/config.py](src/alpha_factory/config.py): **[Suggestion]**
  - `allow_stage_c_fallback_slice` 廃止の fail-closed は設計意図と一致。禁止事項（安易な逃げ道）にも抵触なし。

- [src/alpha_factory/archive.py](src/alpha_factory/archive.py): **[Suggestion]**
  - schema metadata 追記は適切。既存 metadata 保持テストもあり、伝搬漏れリスクは低いです。

- [src/alpha_factory/stage_gate.py](src/alpha_factory/stage_gate.py), [src/alpha_factory/swim_lane.py](src/alpha_factory/swim_lane.py), [scripts/alpha_factory/inspect_stage_b_folds.py](scripts/alpha_factory/inspect_stage_b_folds.py), [src/alpha_factory/stage_b_inconclusive.py](src/alpha_factory/stage_b_inconclusive.py): **[Suggestion]**
  - `bars_18m -> bars_stage_b` の主経路 rename は差分範囲内で接続できています。4段伝搬（config→GaConfig→meta→consumer）で新規パラメータ追加は実質なし、明確な漏れは見当たりません。

**転記漏れ・伝搬漏れ重点チェック結果**
- `config -> GaConfig -> genome.meta -> consumer`: 新規パラメータ追加はなし。`bars_stage_b` rename の呼び出し経路は整合。
- `GENOMES_SCHEMA -> row_template -> collect -> flush`: 新規**カラム**追加はなし（metadata追加のみ）。flush 側の metadata 書き込みは実装・テストあり。
- `summary["stage_b"]` 伝搬: `run_ga` で生成、`generate_run_report` で参照あり。  
- archive metadata 伝搬: `archive.flush()` で付与、テストあり。

**禁止事項チェック**
- 過学習隠蔽のための期間延長、閾値緩和、GAハック、取引回数抑制誘導、オーバーナイト前提化は差分上で確認されません。

**全体判定**
- **CHANGES_REQUESTED**

主理由は 2 点です。  
1. `run_ga.py` の `n_fold_effective` 整数化の型防御不足（将来データ汚染時の落下点）。  
2. `generate_run_report.py` のコメントと実装不一致（運用時の誤解リスク）。
