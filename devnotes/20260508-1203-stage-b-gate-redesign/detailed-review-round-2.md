**レビュー前提**
- 前提 verified: 本レビューは貼付された詳細設計全文と現行コード抜粋のみを根拠にする。ローカル `Read` / grep / git 履歴確認は実施していないため、「最新 main と完全一致」は未検証。
- 前提 verified: `StageGateConfig.stage_b_median_oos_sharpe_min=0.05`、`stage_c_holdout_days=60`、`archive.trade_count` 既存列、`evaluate_stage_b` fold ループ、`_update_cache` の `trade_count` 参照は貼付抜粋上確認済み。
- 前提 assumption: 概念設計 v2 は APPROVED 済みとして扱う。ただし詳細設計で概念から逸脱・未定義・矛盾がある箇所は指摘対象にする。
- 前提 literature: Lo (2002) “The Statistics of Sharpe Ratios”、Bailey and López de Prado (2014) “The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality” を前提文献として扱う。タイトルは記憶ベースのため厳密表記は要確認。

**施策 1**
前提
- verified: 変更対象は `config/alpha_factory/default.yaml` と `StageGateConfig.stage_b_median_oos_sharpe_min` の `0.05 → 0.025`。
- verified: `live_criteria` は変更しない設計であり、Stage B 内部 gate の閾値変更に限定されている。
- verified: run-52 の mission-eligible 7 個体という実測が補足されているが、n=7 のため C7 により因果 claim は禁止。

Fact
- `0.025` は Stage B 内部閾値であり、`live_criteria.sharpe_min` / `trade_count_min` の直接緩和ではない。
- 設計コメントは Lo (2002) の Sharpe SE 近似に基づき、`N=10`、10-fold median SE 近似、真値 SR=0.05 の検出力 50%→60% という説明を追加する。
- テスト計画には既存 hard-coded 値更新、確率 sanity test、run-52 replay test が含まれている。

Interpretation
- North Star に対しては、Stage B の noise-floor と閾値を整合させ、Stage B で過剰に落としている可能性を減らす施策として妥当。
- ただし 10-fold median の SE を単純に `0.32 / sqrt(10)` と置くのは近似であり、fold 間依存・median の分散係数を無視している。設計コメントでは「厳密な検出力」ではなく「heuristic / sanity」と明記する方がよい。
- run-52 の 7 個体は n<10 なので、「この閾値なら使命達成候補が増える」という一般化は不可。replay fixture の限定観察として扱うべき。

反証結果
- 反証 H1: `0.025` は live_criteria 緩和ではないか。結果: 直接は緩和ではない。Stage B 内部 gate のみなので禁止事項 4 には直ちに抵触しない。
- 反証 H2: 検出力 60% の根拠が過度に強いのではないか。結果: 部分的に成立。近似の仮定が強いため、コメントとテストは「確率計算 sanity」に留めるべき。
- 反証 H3: テストが flaky になるのではないか。結果: 成立可能性あり。乱数 simulation で「~60%」を検証すると揺らぐため、固定 seed + 広い許容幅、または `norm.cdf` の決定的計算テストにすべき。

指摘
- [Warning] `test_stage_b_median_threshold_at_noise_floor` は確率 simulation ではなく、Lo 近似式から `Phi(0.25)` を決定的に検証するテストにする。修正案: seed 付き Monte Carlo は補助に留め、主テストは `z = (0.025 - 0.05) / 0.10` と `norm.cdf(-z)` の範囲確認にする。
- [Warning] run-52 replay の n=7 を因果的根拠にしない。修正案: テスト名・コメントを「run-52 fixture 上の blocked candidate 再分類確認」に変更し、一般化 claim を避ける。
- [Suggestion] 設計コメントの「検出力 60%」は「Lo 近似に基づく heuristic」と明記する。

判定: APPROVE  
- 条件: 上記 Warning は実装時に反映すること。設計方向は妥当。

**施策 2**
前提
- verified: 既存 `archive.trade_count` は nullable=False で存在し、T044 補足では Stage A 値固定契約とされている。
- verified: 現行 `collect_stage_b` 抜粋には `payload.trade_count` があれば `row["trade_count"] = tc` とする経路が残っている。
- verified: `_update_cache` は現行 `row.get("trade_count", 0) or 0` で feasible を判定している。
- assumption: Stage A と Stage B は stage partition guard により時系列 disjoint なので、`stage_a_unique + stage_b_full_unique` は重複 timestamp を持たない前提。

Fact
- 新列 `trade_count_stage_a`、`trade_count_stage_b`、`trade_count_full_dataset` は archive schema / template / collect に追加される。
- `evaluate_stage_b` 冒頭で Stage B 全期間の 1 pass backtest を追加し、fold 合算ではなく `trade_count_stage_b` を得る設計。
- `trade_count_full_dataset` が null の場合は旧 `trade_count` に fallback する設計。
- selection schema は `v3_3_stage_b_feasible_priority → v3_4_full_dataset_feasibility` に bump するが tuple 構造は維持。

Interpretation
- Stage B fold 合算を避け、Stage B 全期間 1 pass の trade count を採用する方針は正しい。fold overlap / embargo / unavailable fold による重複・欠落の混入を避けられる。
- ただし詳細設計には archive の既存 `trade_count` 契約と実装抜粋の矛盾が残っている。ここを明示的に潰さないと、`trade_count_stage_a` と既存 `trade_count` の意味が再び曖昧になる。
- `None` fallback だけでは pandas / pyarrow の `NaN` / `pd.NA` に対応できず、旧 archive や full-pass failure の fallback が壊れる可能性が高い。
- Stage B 全期間 backtest の追加コスト `~10%` は未検証。貼付抜粋上 `stage_b_window_months=18` と詳細設計中の `~67日` が整合しておらず、C4 前提不一致がある。

反証結果
- 反証 H1: Stage B full pass は fold ループと重複して無駄ではないか。結果: 完全な無駄ではない。目的が canonical trade count なので fold backtest の総和では代替不可。
- 反証 H2: graceful fallback は安全か。結果: 部分的に否定。`None` のみ扱う実装案では `NaN` fallback が効かず、legacy archive の feasible が偽陰性化する恐れがある。
- 反証 H3: archive 4 段伝搬は満たされているか。結果: 不十分。schema / template / collect は書かれているが、既存 `trade_count` 上書き経路の撤去または無害化が明記されていない。
- 反証 H4: top-K over-trading 比率 20% 低下 test は妥当か。結果: 注意が必要。top-K は selection conditioning set であり collider bias の温床なので、因果 claim ではなく replay 上の順位変化検査に限定すべき。

指摘
- [Critical] `collect_stage_b` の既存 `row["trade_count"] = tc` 経路が T044 の「Stage A 値固定」契約と矛盾している。修正案: Stage B/C の `collect_*` では既存 `trade_count` を上書きしない、または payload の `trade_count` を Stage B 用に使わず `trade_count_stage_b` のみ参照する。追加テストとして `collect_stage_b_does_not_overwrite_stage_a_trade_count` が必要。
- [Critical] fallback 判定が `None` のみだと `NaN` / `pd.NA` を取り逃がす。修正案: `_coerce_optional_int(row.get("trade_count_full_dataset"))` のような helper を用意し、`None`、`NaN`、`pd.NA`、非有限値を null 扱いにしてから `trade_count` に fallback する。
- [Warning] `IndividualCacheEntry.trade_count_full_dataset` を追加する設計だが、提示された `_update_cache` constructor 変更には値の受け渡しが明示されていない。修正案: `trade_count_full_dataset=trade_count_full` を必ず渡し、selection replay / report で観測可能にする。
- [Warning] Stage B full pass のコスト見積り `~10%` は `stage_b_window_months=18` と `~67日` の不一致により未検証。修正案: 実装前に Stage B bars 数 / fold test bars 総数 / 追加 backtest 比率をログまたはテスト fixture で確認し、docs の見積りを修正する。
- [Warning] `test_run_52_replay_selection_with_full_dataset` の「over-trading 比率 20% 以上低下」は C3/C7 上、因果 claim にしない。修正案: 「特定 fixture における ordering regression test」として、conditioning set を `Stage A pass + archive replay top-K` と明記する。

判定: REQUEST_CHANGES  
- 理由: `trade_count` 上書き契約の矛盾と null fallback 不備は selection を直接壊す可能性がある。

**施策 3**
前提
- verified: 既存 archive には `dsr` 列が nullable=True で存在し、現行 `metrics_envelope.payload["dsr"]` は `None`。
- verified: 詳細設計では新規 `src/alpha_factory/dsr.py` を作り、DSR は Phase 1 monitor only とする。
- verified: 設計は `n_trials = 同一 RUN Stage A pass 個体数` とし、GA loop 中は incremental、post-hoc replay では final count で再計算可能としている。
- assumption: scipy は pyproject に既存とされているが、貼付情報ベースでありローカル確認はしていない。

Fact
- helper の docstring は `V[SR]: trial 間の SR 分散` と書いている。
- 実装案では `var_sr = np.var(fold_sharpes, ddof=1)` としており、trial 間分散ではなく同一個体の fold 間分散を使っている。
- 実装案では `scipy.stats.kurtosis(..., fisher=True)` を使い、その値を `((ku - 1.0) / 4.0)` に投入している。
- valid 条件の説明は「全 fold で trade>=30 かつ skew/kurt 有限」だが、コード案は finite な skew/kurt fold だけを採用し、少なくとも 1 つあれば `skew_med` / `kurt_med` が非 None になり得る。
- `evaluate_stage_b` 側の説明には `stage_config.dsr_n_trials_for_run` と `dsr_n_trials_so_far` の 2 つの伝搬案が混在している。

Interpretation
- DSR を monitor only として archive に入れる方針自体は妥当。Phase 2 hard gate 化前に分布を観測するのは design-first に合っている。
- ただし提示コードは Bailey and López de Prado (2014) の式の実装として危険。特に kurtosis の定義と `V[SR]` の出所が設計文とコードで矛盾している。
- 現状のまま `dsr_method="bailey_lopez_de_prado_2014_per_fold_median"` と記録すると、実際には「fold median SR + fold variance approximation」であり、method 名が機能の名前に反する。
- monitor only でも archive に誤定義の DSR を残すと、Phase 2 hard gate 化時に誤った根拠データとして使われる副作用が大きい。

反証結果
- 反証 H1: `norm.cdf` なので DSR は [0,1] に収まるか。結果: 有限 z なら成立。ただし式の入力が誤っていても [0,1] には収まるため、範囲テストだけでは正確性を保証しない。
- 反証 H2: Fisher excess kurtosis の利用は正しいか。結果: 否定。式の `kurt` が通常の Pearson kurtosis なら、`fisher=True` の値を使う場合は `ku_excess + 3` に戻すか、係数を `((ku_excess + 2) / 4)` に変換する必要がある。
- 反証 H3: `V[SR]` は fold variance でよいか。結果: 詳細設計内の説明とは矛盾。trial 間 SR 分散を使う設計なら、同一 RUN の Stage A pass 個体群または Stage B 評価個体群の SR 分布から供給する必要がある。
- 反証 H4: valid flag は設計条件を満たすか。結果: 否定。全 fold の skew/kurt 有限性を要求していないため、一部 fold の moment 推定失敗を隠す。
- 反証 H5: n_trials 伝搬は一貫しているか。結果: 不十分。`StageGateConfig` frozen dataclass に runtime mutable な `dsr_n_trials_for_run` を持たせる案と、関数引数で渡す案が混在している。

指摘
- [Critical] kurtosis 定義が式と不整合。修正案: `scipy.stats.kurtosis(..., fisher=False)` を使う、または `fisher=True` を使うなら denominator を `1 - skew * sr + ((excess_kurt + 2) / 4) * sr**2` に変更する。正規分布近似で denominator が `1 + 0.5 * SR^2` になる単体テストを追加する。
- [Critical] `V[SR]` が trial 間分散ではなく fold 間分散になっている。修正案: Phase 1 では `dsr` を計算せず `dsr_valid=False` + component metrics のみ記録する、または GA loop から同一 RUN Stage A pass 個体群の SR 分散を渡す設計に変更する。fold variance を使うなら method 名を `approx_fold_variance` とし、Bailey and López de Prado DSR と呼ばない。
- [Critical] valid 条件が「全 fold skew/kurt 有限」を満たしていない。修正案: `len(skews) == len(fold_returns)` かつ `len(kurts) == len(fold_returns)` を valid 条件に追加し、returns / sharpes の fold 対応関係も検証する。
- [Warning] `fold_returns_per_fold` と `effective_oos` の長さ・順序対応が未定義。修正案: fold loop 内で `DsrFoldInput(sharpe, returns, trade_count, available)` を作り、available fold のみを同じ構造から抽出する。
- [Warning] `stage_config.dsr_n_trials_for_run` と `dsr_n_trials_so_far` が混在している。修正案: config ではなく `evaluate_stage_b(..., dsr_n_trials_so_far: int)` の明示引数に統一する。runtime 値を frozen config に混ぜない。
- [Warning] incremental n_trials による順番依存値は monitor only なら許容できるが、report では `incremental` と `posthoc_run_total` を混同しない。修正案: archive に `dsr_n_trials_mode="incremental_stage_a_pass_so_far"` を追加するか、report に明記する。
- [Suggestion] DSR archive replay test は final RUN count で再計算する deterministic helper を別途用意し、GA loop 中の incremental 値との差分を仕様として確認する。

判定: REQUEST_CHANGES  
- 理由: DSR 数式実装の定義ズレが大きく、monitor only でも誤った archive データを蓄積するリスクが高い。

**施策 4**
前提
- verified: 現行 `validate_stage_partition` は input / chronological / timestamp disjoint の 3 検証のみ。
- verified: `StageGateConfig.stage_c_holdout_days=60` に対して、設計上は実態 14 日 holdout の不整合を fail-closed で表面化させる意図。
- verified: escape hatch は `--allow-holdout-short` と `ZENIGAME_FX_SMOKE_TEST=1` の二重 opt-in。
- assumption: graduate / calibrate / report の各経路に `holdout_short_override` context を渡せる構造が存在するかは貼付抜粋では未検証。

Fact
- holdout length は `bars_holdout[-1].bar_time - bars_holdout[0].bar_time` の calendar span で評価し、`expected_days * 0.8` 未満なら fail。
- override 有効時は warning のみで通し、summary / report / archive に marker を残す設計。
- production では archive flush 時に `holdout_short_override=True` を拒否する追加 guard が提案されている。
- flush snippet には `env != "smoke"` が出てくるが、`env` の定義・渡し方は詳細設計内で未定義。

Interpretation
- fail-closed guard と二重 opt-in は方向として妥当。短い holdout を通常 RUN として graduate / calibrate に混入させない設計は North Star に合う。
- ただし production / smoke 判別の SSOT が曖昧。`run_ga.py` では env var と CLI の組み合わせで `holdout_short_override` を作るが、`archive.flush` では未定義の `env` に依存している。
- archive への marker 伝搬も `row["holdout_short_override"] = holdout_short_override` と書かれているだけで、archive collector の責務境界上どこで全 row に注入するかが不足している。
- `ZENIGAME_FX_SMOKE_TEST=1` が立っている環境は operationally smoke と扱う設計でよいが、その場合でも graduate / calibrate skip が同一 marker を SSOT にして強制される必要がある。

反証結果
- 反証 H1: holdout length guard は期間延長禁止に抵触するか。結果: 抵触しない。期間を延ばすのではなく不整合を検出する guard。
- 反証 H2: override が production に混入し得るか。結果: 現設計では成立可能性あり。`env` 未定義、flush への伝搬不明、`np.bool_` 等の bool 判定漏れが残る。
- 反証 H3: archive 4 段伝搬は満たされているか。結果: 不十分。schema / template はあるが、collect / run context / flush の責務が曖昧。
- 反証 H4: graduate / calibrate / report 禁止は十分か。結果: 方針は妥当だが、各 module への context 伝搬とテスト対象が必要。現時点では設計の接続部が薄い。

指摘
- [Critical] `archive.flush` の `env` が未定義で、production / smoke 判別の SSOT がない。修正案: `ArchiveWriter` または `flush(..., smoke_test: bool)` に明示引数を追加し、`run_ga.py` で `smoke_test = args.allow_holdout_short and os.environ.get("ZENIGAME_FX_SMOKE_TEST") == "1"` を渡す。archive 内で直接 env を読む場合も helper 化し、テストで monkeypatch する。
- [Critical] `holdout_short_override` の archive 伝搬が不足。修正案: run context → `collect_stage_a` / `collect_stage_b` payload または archive writer constructor → `_create_row_template` → row → `flush` の一本化された伝搬経路を明記する。直接 `row[...]` を run_ga から触る設計は避ける。
- [Critical] smoke override の RUN が graduate / calibrate に到達しないことを単一 marker で保証する必要がある。修正案: `summary["holdout_short_override"]` ではなく、run context の `holdout_short_override` を graduation / calibrate / report に直接渡し、archive flush でも同じ値を検証する。
- [Warning] `any(o is True for o in overrides)` は `np.bool_(True)` や pandas bool を取り逃がす可能性がある。修正案: `normalized = {None if o is None else bool(o) for o in overrides}` のように正規化してから判定する。
- [Warning] `report_filename = "[SMOKE]-run-X.md"` は shell glob で扱いにくい。修正案: `SMOKE-run-X.md` か `run-X-smoke.md` にする。
- [Suggestion] holdout span は first/last 差分だけでなく、必要なら trading day count / unique date count も report に記録すると、週末混入時の診断が容易になる。

判定: REQUEST_CHANGES  
- 理由: 二重 opt-in の方針は良いが、production/smoke 判別と archive marker 伝搬が未定義で、安全弁としてまだ閉じていない。

**波及変更**
- Fact: 施策 1 は `docs/alpha_factory/sharpe-rescale.md` と `docs/alpha_factory/stage-gates.md` の更新を含む。
- Fact: 施策 2 は `AGENTS.md` と `docs/alpha_factory/stage-gates.md` の更新を含む。
- Fact: 施策 3 は `AGENTS.md` と `docs/alpha_factory/stage-gates.md` の更新を含む。
- Fact: 施策 4 は `AGENTS.md` と `docs/alpha_factory/runbook.md` の更新を含む。
- Interpretation: docs の更新対象は概ね妥当。ただし `stage-gates.md` に `trade_count_full_dataset`、DSR の正確な数式、`holdout_short_override` の非 graduate 契約を SSOT として集約すべき。
- [Warning] skill 更新なしの判断はやや弱い。修正案: `.claude/skills/zenigame-fx-run-alpha-factory`、`zenigame-fx-analyze-run`、`zenigame-fx-run-report` 相当が存在するなら、smoke override と DSR monitor の扱いだけは確認対象にする。

**実装モード**
- Fact: 施策 1→2→3→4 の incremental worktree 実装、各段階 commit/test/review は設計されている。
- Interpretation: 段階適用は妥当。特に施策 2 と 3 は selection と archive schema に触るため、同時投入すると原因帰属が濁る。
- [Warning] schema bump は `v3_4_full_dataset_feasibility` の後に DSR monitor が入るなら、archive schema version / selection_score schema / genome_entry_schema_version のどれを bump するのかを分離して明記する。修正案: selection tuple の bump と archive parquet schema の追加列を別名で管理する。
- 判定: APPROVE with Warning

**全体判定**
- 全体判定: CHANGES_REQUESTED
- 主要理由: 施策 2 の `trade_count` 契約矛盾と null fallback 不備、施策 3 の DSR 数式実装不整合、施策 4 の production/smoke 判別未定義が blocking。
- 承認可能な部分: 施策 1 の閾値変更方針、施策 2 の Stage B full 1 pass count 方針、施策 4 の fail-closed + 二重 opt-in 方針。
- 次の修正優先度: `施策2 trade_count契約修正` → `施策3 DSR式/命名/valid条件修正` → `施策4 smoke判別SSOT化` → `施策1テストの非flaky化`。