本分析の前提（C4）
- Verified: Round 1 review と修正対象ファイルを読み、blocker H4 の修正経路を再確認しました。
- Verified: `reserve_run_slot` は advance 後の `current_epoch_index` から `current_window` を再計算し、その window に対して `dataset_cfg` を検証する順序に変わっています。
- Verified: 本レビューでは `pytest/ruff/mypy` は再実行せず、提示された 39 pass / 1210 pass / ruff / mypy clean を前提証跡として扱います。

**結論**
- Round 1 blocker は解消済みです。
- PR 1 の main merge を妨げる FAIL は見つかりません。
- 現作業木には `reports/` 系 untracked が残っているため、コミット対象限定だけ注意してください。

**Round 2 新規観点**
| 観点 | 判定 | 根拠 |
|---|---|---|
| A1 advance/非advance順序 | PASS | `_verify_compatibility` 後に cap/advance、続いて post-advance の `current_window` で `_verify_dataset_match` 実行。`src/alpha_factory/epoch_manager.py:263` |
| A2 `cfg_e1` advance pass | PASS | 7回目 reserve に `cfg_e1` を渡すテストへ更新済み。`tests/alpha_factory/test_epoch_manager.py:214` |
| A3 `cfg_e0` advance mismatch | PASS | 旧 window cfg のまま 7回目 reserve で `EpochDatasetMismatch` を期待する新規テストあり。`tests/alpha_factory/test_epoch_manager.py:231` |
| A4 `EpochCapExceeded` 条件維持 | PASS | `slots_consumed >= MAX_RUNS_PER_EPOCH` かつ `next_window.end > horizon` で dataset match 前に raise。`src/alpha_factory/epoch_manager.py:272` |
| B1 `except ValueError` narrowing | PASS | `EpochWindow.__post_init__` の想定例外型と整合。`src/alpha_factory/epoch_manager.py:117`, `scripts/alpha_factory/run_ga.py:1149` |
| B2 fallback tradeoff | PASS | `make_epoch_id` は `strftime` のみで、想定外例外を握らない方針は妥当。`src/alpha_factory/epoch_manager.py:146` |
| C1 H4 verifying test | PASS | blocker の反証条件を直接テストしている。`tests/alpha_factory/test_epoch_manager.py:231` |
| D 39 tests | PASS | `def test_` は 39 件。ユーザー提示の pass 結果と整合。 |
| E regression/ruff/mypy | PASS | ユーザー提示の 1210 pass / ruff / mypy clean を前提証跡として受理。 |

**A1-G4 判定**
| 観点 | 判定 | 根拠 |
|---|---|---|
| A1 | PASS | `EpochWindow(frozen)` + `end > start` 強制。`src/alpha_factory/epoch_manager.py:103` |
| A2 | PASS | `epoch_YYYYMMDD_YYYYMMDD` は grammar 適合。`src/alpha_factory/epoch_manager.py:146` |
| A3 | PASS | `_compute_window` は anchor + stride で決定論的。 |
| A4 | PASS | advance 後 window で dataset match するよう修正済み。`src/alpha_factory/epoch_manager.py:291` |
| A5 | PASS | `Z`/`+00:00` 正規化あり。 |
| A6 | PASS | 全 epoch 走査で `run_id` 重複拒否。`src/alpha_factory/epoch_manager.py:295` |
| A7 | PASS | corrupt state reset は audit 記録して継続。 |
| A8 | PASS | `reset` は lock 保護。 |
| A9 | PASS | `_init_state` instrument guard あり。 |
| A10 | PASS | `fcntl` 前提は設計側で明示済み。 |
| B1 | PASS | 38計画 + blocker追加 1 = 39 テスト。 |
| B2 | PASS | multiprocess lock test は `spawn`/timeout/terminate で管理。 |
| B3 | PASS | duplicate と corrupt reset の Round1 Critical テストあり。 |
| B4 | PASS | テスト名は振る舞いベース。 |
| B5 | PASS | `tmp_path`/`monkeypatch` 中心で isolation 良好。 |
| C1 | PASS | `ValueError` のみ fallback に narrowing 済み。`scripts/alpha_factory/run_ga.py:1145` |
| C2 | PASS | 同じ `cfg.dataset.start/end` から同じ epoch id。 |
| C3 | PASS | fallback 時のみ warning、主経路は既存 `ga.run.start` に出力。 |
| C4 | PASS | 下流へ渡る型は単一 `str` のまま。 |
| C5 | PASS | Phase 2 申し送りコメントあり。`scripts/alpha_factory/run_ga.py:1136` |
| D1 | PASS | T058 caller signature / SSOT 規範は維持。 |
| D2 | PASS | `schema_version: "1.1"` は維持。`tests/scripts/test_run_ga_parallel.py:254` |
| D3 | NIT | `reports/` 系 untracked が残存。コミット対象限定で回避可能。 |
| E1 | PASS | module-level + wrapper は SSOT を崩していない。`src/alpha_factory/epoch_manager.py:220` |
| E2 | PASS | `run_ga.py` stub 置換は今回のユーザー指示で妥当。 |
| F1 | NIT | PR commit 時に 6実装ファイル + 必要 devnotes のみ add する運用確認が必要。 |
| F2 | PASS | ついでリファクタ混入は見当たらない。 |
| G1 | PASS | dev server 起動はなし。 |
| G2 | PASS | テスト命名規則に適合。 |
| G3 | PASS | 永続 path 汚染はテスト設計上なし。 |
| G4 | PASS | 提示された ruff/mypy/test clean を受理。 |

**Residual NITs**
- `reports/calibrate-gate/history.jsonl` と `reports/run-reports/run-1/diagnostics/` は commit 対象から除外してください。
- hard-coded `_EXPECTED_EPOCH_ID` は契約明示として許容。fixture dataset を変える場合は関連 smoke 契約も同時更新が必要です。

[APPROVED with NITs]