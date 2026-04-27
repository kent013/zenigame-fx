**指摘事項（重要度順）**
- [Critical] [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/scripts/alpha_factory/run_ga.py)  
  `preflight` は `stage_b_window_months / holdout` を考慮した拡張期間で検証している一方、`build_aux_bundle_from_db()` は `cfg.dataset.start/end` のみで読み込んでいます。  
  そのため、Stage B/C で必要な過去区間が `aux_bundle` に載らず 0 埋め経路に落ちる可能性があり、`preflight pass` と実評価データが不整合になります（値伝搬漏れリスク）。
- [Critical] [migration 004](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/src/db/migrations/versions/004_macro_index_daily_effective_from.py)  
  migration が `src.ingest.effective_from.compute_effective_from_utc` を直接 import しています。将来この関数が変更されると、同じ revision `004` の挙動が環境/時期で変わるため、migration の再現性が壊れます。  
  migration 内に計算ロジックを固定化すべきです。

- [Warning] [aux_preflight.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/src/alpha_factory/aux_preflight.py)  
  `PriceBarM1` の coverage 計算が `select(...).all()` → `len()` で全件ロードになっており、18ヶ月M1ではメモリ/速度コストが高いです。`COUNT(*)` に置き換えるべきです。
- [Warning] [test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/tests/scripts/test_alpha_factory_run_ga.py)  
  `len(created) == 1` から `>= 1` へ緩めたことで、セッション増加や preflight 経路の回帰を検知しにくくなっています。T057 の重要経路としては弱いです。
- [Warning] [test_aux_preflight.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/tests/alpha_factory/test_aux_preflight.py)  
  V13（両端 freshness）を明示検証する stale-tail ケースが不足しています（`latest_effective_from < extended_end - safety_lag` の失敗検証が見当たらない）。

- [Suggestion] [fetch_aux_data.sh](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/scripts/fetch_aux_data.sh)  
  既定 `END=2026-04-30` は 2026-05 以降すぐ stale 化します。`END` は実行日（UTC/JST）既定にする方が運用事故を減らせます。
- [Suggestion] [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/src/alpha_factory/parallel_eval.py)  
  `_PROC_AUX_CACHE` がプロセス生存中に増え続ける設計です。長寿命 worker 前提なら明示クリア導線があると安全です。

**ファイルごと判定**
- [Critical] [scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/scripts/alpha_factory/run_ga.py)
- [Critical] [src/db/migrations/versions/004_macro_index_daily_effective_from.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/src/db/migrations/versions/004_macro_index_daily_effective_from.py)
- [Warning] [src/alpha_factory/aux_preflight.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/src/alpha_factory/aux_preflight.py)
- [Warning] [tests/scripts/test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/tests/scripts/test_alpha_factory_run_ga.py)
- [Warning] [tests/alpha_factory/test_aux_preflight.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/tests/alpha_factory/test_aux_preflight.py)
- [Suggestion] [scripts/fetch_aux_data.sh](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/scripts/fetch_aux_data.sh)
- [Suggestion] [src/alpha_factory/parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T057/src/alpha_factory/parallel_eval.py)
- [APPROVED相当] 上記以外の差分ファイル（`aux_loader.py`, `effective_from.py`, `ingest/fred.py`, `config/stage_gate`, テスト追加群）は設計意図と概ね整合

**重点チェック結果**
- config → consumer 伝搬: `strict_aux_required` は `default.yaml → config.py → StageGateConfig → run_ga` で伝搬確認。  
- `GENOMES_SCHEMA` 4点セット: 今回差分では新規ゲノム列追加なし（該当なし）。  
- logger 追加: preflight 系ログは追加済みだが、新規列書き込み（例: FRED upsert）の粒度ログは薄め。

**全体判定**
- **CHANGES_REQUESTED**