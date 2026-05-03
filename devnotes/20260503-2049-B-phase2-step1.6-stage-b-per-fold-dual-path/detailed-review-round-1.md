使用スキル: `zenigame-codex-review`（レビュー規約のみ参照）。  
Round 1（Falsification-first）として、設計文書・実コード・既存テスト・git履歴を先に確認して反証を探しました。

**前提検証 (C4)**
- Verified: 既存 `evaluate_stage_b` は `n_fold = len(folds)` の動的設計で、fold数は固定5ではありません。[stage_gate.py:810](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:810)
- Verified: fold数は `compute_max_folds` の式で決まり、`train/test/step/embargo` と観測日数依存です。[walk_forward.py:66](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py:66)
- False: 設計書の「`_make_continuous_bars(20)` + `wf_train=3,wf_test=2,wf_step=2` で5fold」は式と整合しません（この条件は8fold）。[detailed-design.md:478](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md:478) [test_stage_gate.py:86](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate.py:86) [test_stage_gate_canonical_dual_path.py:468](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:468)
- Verified: 既存callerは `_log_canonical_dual_path` をすべてkeyword呼び出ししており、optional kwarg追加の後方互換性は高いです。[stage_gate.py:655](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:655) [stage_gate.py:857](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:857) [stage_gate.py:1234](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1234)

**主要指摘**
- [Critical] 5fold固定前提が崩れており、acceptance/テスト仕様がそのままだと誤判定になります。  
修正案: `0..4` 固定表現を全て `0..n_fold-1` に変更し、テストは `make_wf_folds()` で得た `n_fold` と照合してください。必要なら5fold専用fixtureを明示的に作ってください（例: 日数を13に調整）。
- [Critical] D3テスト案（helperをraiseに差し替えてdisabledとdeep一致）は現行構造では成立しません。  
Fact: `evaluate_stage_b` は per-fold前に `B_IS` でも同helperを呼びます。[stage_gate.py:844](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:844)  
Interpretation: helperを無条件raiseにすると `is_full_*` が変わり、disabled比較が崩れます（step1.5でも同問題を明記済み）。[test_stage_gate_canonical_dual_path.py:534](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:534)  
修正案: monkeypatchを `stage_label=="B_fold"` 限定raiseにするか、B_IS呼出を透過させるラッパーで比較してください。
- [Warning] D2の文言が実装案と不一致です。  
Fact: 仕様D2は「unexpected_failureのみ」と記述。[detailed-design.md:511](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md:511)  
Fact: 実装案は `log_failed` も出します。[detailed-design.md:311](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md:311)  
修正案: D2を「`unexpected_failure` または `log_failed`」に更新。
- [Warning] C5（`canonical_skipped=True`でもfold必須）の専用テストが明示不足です。  
修正案: disabled modeで `stage='B_fold'` 行を全件抽出し、全行に `fold=` があることを検証するテストを追加。
- [Suggestion] 性能/ログ量見積もりを5fold固定から動的化してください。  
修正案: `追加log件数 = n_fold`、`追加計算 = n_fold` で記述し、B3は `n_fold` をメトリクスとして併記。

**施策別判定**
1. 施策1 `_log_canonical_dual_path` optional kwarg + B_fold契約: **APPROVE**  
[Warning] D5 fail-fastは妥当。ただし運用契約としては `canonical_skipped` 経路のfold必須検証をテストで固定してください。
2. 施策2 `evaluate_stage_b` per-fold dual-path別try配線: **REQUEST_CHANGES**  
[Critical] 設計内の5fold固定前提（性能・運用見積もり・acceptance文言）が実コード仕様と不整合。  
[Warning] D2文言が実装案ログ種別と不一致。
3. 施策3 8ケーステスト計画: **REQUEST_CHANGES**  
[Critical] D3案が現行呼出順（B_IS先行）と衝突。  
[Critical] 5fold固定のlog contentテストはfixture条件と整合しない。  
[Warning] C5専用検証が不足。

**C1-C9チェック要約**
- C1 Design-first: 実施（devnotes→コード→git履歴の順で確認）。
- C2 並行経路確認: 実施（A/B_IS/C_base/B_foldの呼出経路を分離確認）。
- C3/C7 collider bias・サンプル: 設計方針は概ね適切（因果主張なし）。
- C6 Fact/Interpretation分離: 上記各指摘で分離記載。
- C8 INCONCLUSIVE: 実測性能（B2/B3）は設計時点では未確定。
- C9 Falsification-first: 主仮説は「物理隔離」は概ね成立見込み。ただし受け入れ条件とテスト設計に反証点あり。

**全体判定**
- **CHANGES_REQUESTED**  
主因は「5fold固定前提の破綻」と「D3テスト設計の不成立」です。ここを修正すれば、物理隔離アーキテクチャ自体は妥当です。  

（read-only制約のためテスト実行はしていません）