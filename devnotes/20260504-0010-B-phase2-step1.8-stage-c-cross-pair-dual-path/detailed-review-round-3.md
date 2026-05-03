**本分析の前提**
- Verified: 提示されたRound 3詳細設計テキストを対象にレビュー。
- Unverified: 実ファイルのgrep、`git log -S`、ruff/mypy、pytest、smoke実行は未確認。
- Verified: 相関・因果claimは実質なく、C3/C7の追加論点はなし。

**Facts**
- Round 2の主要論点だった`pair_label`契約、`metric_unavailable`契約、disabled mode文言、uv smokeは概ね反映済み。
- `dual-path skip`のSSOTを`sidecar_inputs is None`に置き直したことで、`pair_failures`とdual-path観測の責務分離は明確になった。
- ただし、§2の主要決定と§8.4コードコメントに古い文言が残っている。

**Interpretations**
- 実装方針そのものは採用可能な水準。
- 残る反証ポイントは「設計本文の古い契約が実装者を誤誘導する」ことと「B2メモリgateが元の1 worker 3GB制約を直接検証しない」こと。

---

## 施策別判定

**施策1: `_PairSidecarInputs`追加**
- 判定: **APPROVE**
- [Suggestion] `BrokerTrade` import元は実装時に型実体と一致確認が必要。`Trade as BrokerTrade`が既存型名とズレるとmypyだけでなく読解コストが増える。

**施策2: `_log_canonical_dual_path`拡張**
- 判定: **APPROVE**
- `None` / 空文字 / 空白 / 前後空白 / non-C_cross_pair指定を拒否しており、識別子契約は十分に厳密。
- [Suggestion] エラーメッセージが長いため、テストでは全文一致ではなく主要部分一致にする方が保守しやすい。

**施策3: `_run_pair_sharpe` 3-tuple化**
- 判定: **APPROVE**
- `sidecar_inputs is None`をdual-path skip条件にした整理は妥当。
- `metric_unavailable`をcross_pair gate上は失敗、dual-path上は観測対象にする分離も責務として整合。

**施策4: `evaluate_cross_pair` sidecar集約**
- 判定: **APPROVE**
- aggregation経路とsidecar経路が分離されており、metrics汚染も避けられている。
- test #16のdeep equalityで既存public metricsの非干渉を固定する方針も妥当。

**施策5: `evaluate_stage_c` dual-path + sanitize**
- 判定: **REQUEST_CHANGES**
- [Warning] §8.4コードコメントに「disabled mode 軽量分岐 (= per-pair iterate を skip、軽量 log のみ emit」と古い矛盾文言が残っている。実コードはiterateするため、実装者が誤読する。
- 修正案: コメントを「per-pair iterate は走るが canonical 計算のみ skip、軽量 log を emit」に統一。
- [Warning] §2の主要決定に「pair_failure pairでdual_path emitされない」という古い契約が残っている。Round 3のSSOTと衝突する。
- 修正案: §2を「`sidecar_inputs is None`のpairのみemitしない。`metric_unavailable`はcanonical_skipped emit対象」に更新。

**施策6: テスト + smoke**
- 判定: **REQUEST_CHANGES**
- [Warning] §12.3のB2判定が`process_tree_peak_rss < 24GB`になっており、元の制約「6 worker / 1 worker最大約3GB」に対する直接検証ではない。これだと1 workerが3GB超でも総量が24GB未満なら通過し得る。
- 修正案: merge gateを少なくとも`process_tree_peak_rss < 18GB`にするか、`psutil`等でworker別RSSを取得して`max_worker_rss < 3GB`をB2本体にする。
- [Warning] `/usr/bin/time -l`の`maximum resident set size`を「process tree全体の合計peak」と解釈するのは要確認。macOS/BSD系では子プロセス最大値の扱いが合計とは限らない。
- 修正案: 指標説明を「time -l由来の参考RSS」に弱めるか、集計helperで実測方法を明示する。

---

## 横断判定
- ルックアヘッドバイアス: **APPROVE**。既存backtest結果の観測追加であり、未来参照の新経路は見当たらない。
- メモリ制約: **REQUEST_CHANGES**。smokeの閾値が元の1 worker 3GB制約とズレている。
- パフォーマンス: **APPROVE_WITH_MEASUREMENT**。B3をsmoke実測merge条件にしたため設計上は許容。
- C1/C2: **INCONCLUSIVE**。設計書上のgrep痕跡は改善済みだが、レビュー側では実確認していない。

**全体判定: CHANGES_REQUESTED**

設計本体はほぼAPPROVE水準です。残る修正は小さいですが、§2/§8.4の古い契約文言と§12.3のメモリgateは実装・merge判断に影響するため、Round 3のまま承認はしません。