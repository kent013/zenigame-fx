**主要指摘（重要度順）**
- [Critical] `profit_safe_pfr` の PnL 集計が「effective fold のみ」という設計と不一致です。実装案では `bt.total_pnl` が finite なら `fold_sharpe is None` の fold（= unavailable fold）でも `oos_total_pnls` に入ります。これにより `median_oos_total_pnl`/`sum_oos_total_pnl` が unavailable fold を混ぜた値になり、設計条件から逸脱します。該当: [` .codex-impl-diff.txt#L225`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-2007-fx-improve/.codex-impl-diff.txt#L225), [` .codex-impl-diff.txt#L266`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-2007-fx-improve/.codex-impl-diff.txt#L266)  
  修正案: `oos_total_pnls.append(...)` を `fold_sharpe is not None` 側に移動し、effective fold のみ集計する。
- [Critical] `--stage-b-gate-kind` の CLI override が `_resolve_stage_a_threshold()` 後に適用されるため、`compute_base_config_hash` の cross-run guard が CLI override 時に実質効きません。今回 hash に新3項目を入れた意図（mode 切替時の誤適用防止）と矛盾します。該当: `_resolve` 呼出 [`run_ga.py#L1434`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1434)、override 追加位置 [` .codex-impl-diff.txt#L46`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-2007-fx-improve/.codex-impl-diff.txt#L46)  
  修正案: gate_kind override を threshold 解決より前に適用（または `_args_to_overrides` 経由で load_config 時点で反映）。
- [Warning] 新 reason code 追加に対して `tests/scripts/test_generate_run_report_stage_b_reason.py` 側の known_codes 契約テスト更新が見当たりません。実装追従テストを追加した方が安全です。参照: [`test_generate_run_report_stage_b_reason.py#L15`](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_generate_run_report_stage_b_reason.py#L15)

**ファイル別判定**
- `src/alpha_factory/stage_gate.py`: `REQUEST_CHANGES`
- `scripts/alpha_factory/run_ga.py`: `REQUEST_CHANGES`
- `scripts/alpha_factory/generate_run_report.py`: `APPROVE`（上記 Warning あり）
- `src/alpha_factory/config.py`: `APPROVE`
- `src/alpha_factory/calibrate_state.py`: `APPROVE`
- `src/alpha_factory/archive.py`: `APPROVE`
- `tests/alpha_factory/test_archive.py`: `APPROVE`
- `tests/alpha_factory/test_stage_gate.py`: `REQUEST_CHANGES`（Critical 2件を検出できるテスト不足）

**Q1 回答**
- finite guard の legacy 副作用: `fold_sharpe/fold_reason/reason_counts` 自体は触っていないため legacy 判定経路は直接不変です。ただし `profit_safe_pfr` 側の「effective foldのみ集計」契約には違反しています（Critical）。
- `else: raise ValueError`: `__post_init__` で通常阻止されるため防御コードとして妥当です。
- `archive.py` の `isinstance(gate_kind, str)`: 妥当です（defensive）。
- `run_ga.py` の `replace` で frozen 維持: 妥当です。問題は適用順序です（Critical）。

**Q2 テスト網羅性**
- 不足があります。最低でも次を追加推奨です。  
1. unavailable fold（`fold_sharpe is None` だが `total_pnl` finite）を `oos_total_pnls` へ入れないこと。  
2. `--stage-b-gate-kind` 指定時、threshold 解決用 hash が override 後 cfg で計算されること。  
3. run report の known reason codes に T099 追加5件が含まれること。

**Q3 設計一致性**
- 一致している点: mode 分岐、reason code追加、archive 3列追加、config/hash 伝搬方針。
- 不一致: `oos_total_pnls` の集計対象が effective fold 限定になっていない点（Critical）。
- 追加不整合: CLI override の適用順序により cross-run guard 意図を一部損なう点（Critical）。

**Q4 30 RUN 連続ループ影響**
- 「default legacy で完全互換」という主張は概ね妥当です。  
- ただし cycle 22 の `--stage-b-gate-kind profit_safe_pfr` 実行は上記 Critical 2件により評価汚染リスクがあります。修正後なら cycle 23 以降 legacy sweep への影響はほぼありません。

**全体判定**
- `CHANGES_REQUESTED`