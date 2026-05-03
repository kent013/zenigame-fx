**本分析の前提**
- Verified: 提示されたRound 2詳細設計テキストと現行コード断片を根拠にレビュー。
- Unverified: 実ファイルの`docs/devnotes`全文、`git log -S`、実grep、ruff/mypy実行は未確認。ユーザー指定に従いコマンド実行なし。
- Verified: 新規の相関・因果claimはなく、C3/C7のcollider/sample size問題は対象外。

**Facts**
- Round 1の2 Criticalは、設計上は`pair_label`厳密化と`try...finally` sanitizeで反映されている。
- `metric_unavailable`はRound 2でsidecar保持へ変更され、dual-path log対象に戻された。
- sanitizeは`finally`で`cross_pair_payload["result"]`を再取得し、`CrossPairResult`ならsidecarを空dictに差し替える設計になった。

**Interpretations**
- 主要Criticalは解消傾向。ただし、`metric_unavailable`の扱いが既存の「pair_failure pair skip」契約と衝突しており、acceptance/test文言を修正しないと実装者が誤読するリスクが残る。
- メモリ・性能は「merge前実測で判定」に落とせており、設計段階の未確定事項としては許容可能。

---

## 施策別判定

**施策1: `_PairSidecarInputs` + `_shadow_sidecar_inputs`**
- 判定: **APPROVE**
- [Warning] `BrokerTrade` / `Decimal` のimport波及が設計に明記されていない。ruff/mypyで未定義名になる可能性がある。
- 修正案: 施策1の波及変更に`stage_gate.py`の型import追加を明記。
- [Suggestion] E7は「将来のmutation防止」までは保証しないため、テスト名は「現行dual-pathがmutationしない」に寄せると正確。

**施策2: `_log_canonical_dual_path`拡張**
- 判定: **APPROVE**
- [Warning] `pair_label=" EUR_USD "`は通る。実pair名契約なら空白混入も拒否すべき。
- 修正案: `pair_label != pair_label.strip()`も`ValueError`にする。
- [Suggestion] `stage_label != "C_cross_pair"`で`pair_label is not None`なら拒否すると、ログ名前空間汚染をより防げる。

**施策3: `_run_pair_sharpe` 3-tuple化**
- 判定: **REQUEST_CHANGES**
- [Warning] `metric_unavailable`をsidecar保持に変えたため、概念設計の「pair_failure pairではdual_path emitしない」と矛盾している。現行reasonも`pair_failure:{pair}:metric_unavailable`になる。
- 修正案: 「exception pairのみdual-path skip、metric_unavailableはcanonical_skipped emit対象」と契約・acceptance C6・test #4名を更新する。
- [Warning] `_try_evaluate_canonical_five_safe`がno-tradeで必ず`None`を返す前提が未検証。
- 修正案: no-trade/metric_unavailable入力で`canonical_skipped=True`になる単体テストを追加。

**施策4: `evaluate_cross_pair` sidecar集約**
- 判定: **APPROVE**
- [Warning] `pair_failures`に`metric_unavailable`が入る一方でsidecarは保持されるため、後段の「pair_failure pair skip」テストと衝突しやすい。
- 修正案: `sidecar_inputs is None`をdual-path skip条件のSSOTにする、と明記する。

**施策5: `evaluate_stage_c` dual-path + sanitize**
- 判定: **APPROVE**
- [Warning] disabled mode説明に「per-pair iterate全体をskip」とあるが、実コード案はlog emitのためiterateする。
- 修正案: 「canonical計算のみskip、per-pair lightweight logはemit」に文言修正。
- [Suggestion] invalid pair keyはWARN+skipでよいが、これは識別子契約違反なのでtest #25で`_log_canonical_dual_path`未到達も固定するとよい。

**施策6: テスト計画**
- 判定: **REQUEST_CHANGES**
- [Warning] test #4「skips_pair_failure_pair」がmetric_unavailableまで含むのか曖昧。
- 修正案: `exception pair skips dual-path`と`metric_unavailable emits canonical_skipped`を別テストに分ける。
- [Warning] smoke scriptが`python3`直呼びで、プロジェクトルールのuv必須と不整合。
- 修正案: `uv run python scripts/smoke/aggregate_step1.8_memory.py "$LOG_DIR"`に変更。
- [Warning] `/usr/bin/time -l`だけで`peak_rss_max_per_worker`を正確に出せるか不明。
- 修正案: 集計helper側でworker別RSSを取れないなら、指標名を`process_tree_peak_rss`等に変更する。

---

## 横断判定
- ルックアヘッドバイアス: **APPROVE**。primitive変更ではなく、既存backtest結果の観測経路追加に留まる。
- メモリ制約: **INCONCLUSIVE**。見積りとsmoke gateは妥当だが、実測前なので確定不可。
- パフォーマンス: **INCONCLUSIVE**。B3をmerge条件にした点は妥当だが、`+3 canonical calc`が±20%以内に収まるかは実測依存。
- C1/C2: **INCONCLUSIVE**。grep痕跡の記載は改善だが、レビュー側では実確認していない。

**全体判定: CHANGES_REQUESTED**

Round 1のCriticalは概ね解消しています。残る変更要求は、`metric_unavailable`を「pair_failureだがdual-path emitする」扱いに変更したことによる契約・test名・acceptance C6の整合修正です。ここを明確化すれば、設計としてはAPPROVE水準に近いです。