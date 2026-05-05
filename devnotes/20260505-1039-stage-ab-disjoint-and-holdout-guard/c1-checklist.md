# C1 Design-first チェックリスト実施結果（T087）

実施日時: 2026-05-05 11:25 (JST)
worktree: `worktrees/todo-T087`

## チェック 1: docs/alpha_factory/stage-gates.md の Stage A/B/C 契約

- 現状の stage-gates.md は `bars_18m: list[PriceBar]` を引数名として記載（line 77）
- Stage A/B/C 契約の明文化は existing。本詳細設計の `bars_stage_b is disjoint from bars_stage_a` 契約は**未記載**のため追記必要
- 結果: `bars_stage_b` の disjoint 化契約を追記、`bars_18m → bars_stage_b` rename を反映

## チェック 2: docs/alpha_factory/runbook.md の起動シーケンス

- 起動シーケンスの partition guard 言及なし（追記対象）
- aux_preflight との順序関係の明文化必要
- 結果: 「Stage Partition Guard」ステップを runbook 起動シーケンスに追記

## チェック 3: git log -S "bars_stage_b" 履歴

- `efaf365 feat(alpha_factory): T018 run_ga.py full rewrite` で導入
- `deb6b20 feat(T052): GA 評価並列ワーカー数指定機能` ほかで参照拡大
- 意味は run_ga.py 導入時から「[dataset.start, dataset.end) 全期間」だった
- 結果: 本 TODO の「Stage A 期間除外」は**意味の初変更**。stage_gate_version bump（v3 → v4）は妥当

## チェック 4: git log -S "bars_18m" 履歴

- T018 run_ga full rewrite 時から命名されていた識別子
- 当初の stage_b_window_months=18 由来の命名（→ 現在は意味と乖離）
- 結果: rename の合理性が補強された

## チェック 5: git grep -n "bars_18m" 全件確認

合計 31 件、想定通り:
- src/alpha_factory/stage_gate.py: 6 件
- src/alpha_factory/canonical_adapter.py: 1 件
- src/alpha_factory/swim_lane.py: 7 件
- tests/alpha_factory/test_aux_loader_align.py / test_swim_lane.py: 含む
- scripts/alpha_factory/run_ga.py: 1 件（evaluate_stage_b 呼び出し keyword）
- scripts/alpha_factory/inspect_stage_b_folds.py: 4 件

→ 詳細設計の rename スコープ表と一致

## チェック 6: ls devnotes/ 関連検索

- `20260423-2324-run-ga-full-rewrite/` （T018 の元設計、本 TODO の前提元）
- 他に `partition` / `holdout` 名の devnotes は無い（本 TODO が初）

## チェック 7: allow_stage_c_fallback_slice 全件確認

production code:
- `src/alpha_factory/config.py:198, 204, 512-513` （StageWindowsConfig フィールド + load）
- `scripts/alpha_factory/run_ga.py:436, 476, 493` （docstring + fallback 分岐）

tests:
- `tests/fixtures/alpha_factory_min_config.yaml:47`
- `tests/scripts/test_alpha_factory_run_ga.py:220, 542, 630`

→ production 廃止時にテスト側 3 箇所の書き換え対象。fallback を使う `test_alpha_factory_run_ga.py` の関連テストは test-only ヘルパーで `LaneBarsBundle` 直接構築する経路に変更する

## 前提を覆す事実なし → 詳細設計のまま実装着手可
