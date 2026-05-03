**全体判定**

CHANGES_REQUESTED

**前提検証 (C4)**

- Fact: `_build_canonical_thresholds_for_window` は `live_criteria` と `window_days` だけで threshold を決める pure な算術 helper です。[`src/alpha_factory/stage_gate.py#L68-L109`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L68)
- Fact: `make_wf_folds` は calendar day ではなく observed UTC date ベースで fold を切ります。[`src/alpha_factory/walk_forward.py#L72-L164`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L72)
- Fact: 現在の Stage B per-fold は 1 fold ごとに単一の outer `try` で backtest と metrics を包んでいます。[`src/alpha_factory/stage_gate.py#L892-L946`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L892)
- Fact: step 1.5 の approved 文書と handoff では、Stage C cross-pair は step 2 以降の mission 必須軸として残っています。[`devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md) [`devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md)

- Interpretation: 「5 fold で同じ threshold を 5 回作れば一致するか」は yes です。反証点はそこではなく、「20 observed days を `window_days=20` で代表させる意味づけ」と「step 1.6 単独で step 2 前提を完全充足できるか」です。
- Interpretation: 最大の設計リスクは、dual-path が fold 判定に干渉しうる配置になっている点と、前提充足の主張が既存設計史より強すぎる点です。

**1. 使命との整合性**

- [Critical] Fact: 本文は「step 1.6 完了後に step 2 の calibration 前提が完全充足」と述べていますが、approved 済み step 1.5 文書では Stage C cross-pair は mission 必須評価軸のまま未観測です。解釈: `B_fold` を埋めても「全 Stage 全評価軸」は未充足です。修正提案: step 1.6 の成果を「Stage B per-fold OOS canonical 観測の追加」に限定し、「step 2 前提完全充足」は削除して「Stage B 側 calibration data の拡充」に下げてください。

- [Warning] Fact: handoff では step 2 先行が推奨され、step 1.6 は独立な観測拡張と整理されています。解釈: 本設計の位置付けは既存の設計判断と緊張しています。修正提案: 「step 2 を block する必須 step」ではなく「任意だが有益な観測拡張 step」に戻してください。

**2. 禁止事項違反**

- [Warning] Fact: 本設計自体は live_criteria 緩和や期間延長をしていません。解釈: 直接の禁止事項違反は見当たりませんが、「前提完全充足」という強い文言は、後段で per-fold の見かけ値を使って切替を急ぐ誘因になります。修正提案: step 1.6 文書内に「B_fold の pass/fail 分布だけで step 2 切替判断をしない」「live_criteria/評価期間は変更しない」を明文化してください。

**3. 実現可能性**

- [Critical] Fact: 提案擬似コードでは `_try_evaluate_canonical_five_safe(...)` が fold の outer `try` 内に置かれています。現実装の fold loop では outer `try` の例外が `stage_b.fold_failure` となり、`fold_reason=FOLD_EXCEPTION` に落ちます。[`src/alpha_factory/stage_gate.py#L892-L946`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L892) 解釈: helper が「本来 no-raise」であっても、将来の実装ミス・signature 不整合・monkeypatch・logger 以外の想定外例外が起きると、観測 only のはずの追加コードが fold 判定を変えます。Stage B は fold 集計が gate 本体なので、これは IS monitor より重い破壊です。修正提案: legacy fold 計算で `fold_sharpe` / `fold_reason` を確定した後に、dual-path を別 `try` ブロックへ分離してください。canonical 失敗は専用 WARN のみ、`fold_reason` は不変にしてください。

- [Warning] Fact: `_log_canonical_dual_path` への optional kwarg 追加自体は後方互換です。既存 caller はすべて keyword 呼び出しです。[`src/alpha_factory/stage_gate.py#L655-L660`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L655) [`src/alpha_factory/stage_gate.py#L857-L862`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L857) [`src/alpha_factory/stage_gate.py#L1234-L1239`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1234) 解釈: backward compatibility の本当の論点は signature ではなく、log 一意性契約が `genome+stage` から `genome+stage+fold` に変わる点です。修正提案: 既存の log key 契約テストを B_fold 用に拡張し、`canonical_skipped=True` 経路も含めて `fold` 必須を固定してください。[`tests/alpha_factory/test_stage_gate_canonical_dual_path.py#L1039-L1078`](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py#L1039)

**4. 期待効果の妥当性 (C3 / C7)**

- [Warning] Fact: Option 1 で 5 回 threshold を構築しても、同じ `wf_test_days` を渡す限り値は一致します。一方で fold 分割は observed-day ベース、threshold scaling は `window_days` の線形倍率です。[`src/alpha_factory/stage_gate.py#L68-L109`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L68) [`src/alpha_factory/walk_forward.py#L72-L164`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L72) 解釈: Option 1 の妥当性は「5 回で同じ値になる」ことまでは言えますが、「各 fold の実窓に意味的に整合する」までは言えません。修正提案: rationale を「deterministic equality / SSOT 再利用」に限定し、「fold 実窓への意味整合」は未検証前提として切り分けてください。

- [Warning] Fact: canonical 側 trade-count threshold は live_criteria を 20/730 で縮尺するので 20 日 fold では実質かなり低くなり、他方 legacy fold Sharpe 可用性 guard は `stage_b_fold_trade_count_min=10` です。[`src/alpha_factory/stage_gate.py#L89-L109`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L89) [`src/alpha_factory/stage_gate.py#L314-L323`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L314) [`src/alpha_factory/stage_gate.py#L882-L925`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L882) 解釈: legacy fold gate と canonical fold gate は同じものを見ていません。ここから出る pass/fail 差を「threshold 妥当性」や「切替準備完了」と因果解釈すると collider bias を踏みます。修正提案: step 1.6 の期待効果から「calibration 前提を完全充足」を外し、「descriptive observation only」を明記してください。

- [Warning] Fact: 1 genome あたり fold 数は 5 です。解釈: C7 上、genome 単位や single run の per-fold pass pattern は因果解釈禁止です。修正提案: 「解釈単位は run 横断・genome 横断の集計で n>30 を満たした後」と本文に明示してください。

**5. リスク**

- [Warning] Fact: log volume 増加の論点はサイズだけではなく、同一 `stage="B_fold"` 内で 5 entry をどう識別・集計するかです。解釈: `fold` を optional にするだけでは downstream の grep / 集計契約が曖昧です。修正提案: log SSOT に「B_fold は `stage+genome+fold` が識別子」と追記し、`fold` 欠落時は bug 扱いにしてください。

- [Suggestion] Fact: 72,000 entry/run 見積もりは理論上限に近く、実際は Stage 通過率に依存します。解釈: 見積もりとしては粗くても十分ですが、運用影響の根拠としては弱いです。修正提案: acceptance を「entry 数」ではなく「1 run あたり dual-path log bytes / wall time / WARN 率」で置いた方が監査しやすいです。

**6. スコープの適切さ**

- [Suggestion] Fact: `stage_gate.py` のみで閉じる方針自体は妥当です。解釈: この step で adapter や archive schema に触らないのは mission と禁止事項に整合しています。修正提案: その代わり、文書上も「Stage B fold 観測拡張だけ」で止め、step 2 / cross-pair / archive 永続化へ主張を伸ばしすぎないでください。

**7. メモリ制約 (24GB / 6 workers / 1 worker 3GB)**

- [Suggestion] Fact: per-fold canonical は sequential 実行なので、設計の方向としては 5 fold 同時保持ではありません。[`src/alpha_factory/stage_gate.py#L892-L946`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L892) 解釈: 致命的なメモリ破綻は起きにくい一方、`BarEquitySeries` や tuple/set の Python object overhead を考えると「2MB/fold」は楽観的です。修正提案: 概算値はそのままでもよいですが、文言を「上限保証」ではなく「低リスク仮説」に弱めてください。

**8. 前提検証 (C4)**

- [Critical] Fact: 現在の前提表では「threshold 5 回構築の equality」「fold 実窓への意味整合」「step 2 前提完全充足」が混在しています。解釈: verified と unverified が分離されておらず、前提が強すぎます。修正提案: 前提表を少なくとも次の 3 つに分解してください。`(a) 同一入力なら threshold 値は一致する = Verified`, `(b) observed-day fold に window_days=wf_test_days を使う意味整合 = Unverified`, `(c) step 2 に必要な全評価軸観測が揃う = False / 未達`。

- [Warning] Fact: acceptance には `B_fold` の `canonical_skipped=True` path、`fold` 欠落、同 genome 同 stage で 5 fold 全件が区別できることの専用 test が明記されていません。解釈: ここが抜けると「後方互換だったが運用 contract は壊れた」を見逃します。修正提案: B_fold 専用 test を最低 3 本追加前提で設計書に固定してください。

**9. Design-first 原則 (C1)**

- [Suggestion] Fact: step 1.5 の approved 設計と handoff には、今回の反証材料がすでにかなり書かれています。解釈: 本設計はそこを読んだ上で一部の主張だけ再び強めています。修正提案: 既存 approved 文書の制約をそのまま引用し、今回の差分主張を最小化してください。

**結論**

- Option 1 自体は却下理由になりません。同一 `wf_test_days` を渡す限り threshold は 5 回とも同値です。
- ただし、現状のままでは「step 1.6 が step 2 前提を完全充足する」という主張と、「per-fold dual-path 例外が legacy fold 判定に絶対干渉しない」という主張を支持できません。
- 修正の最小セットは 2 点です。`1)` step 1.6 の位置付けを Stage B per-fold 観測拡張に限定する。`2)` per-fold legacy 判定と dual-path 観測を try ブロックで物理的に分離する。これが入れば再レビュー可能です。