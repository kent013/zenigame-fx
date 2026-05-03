**本分析の前提**
- Verified: 提示されたRound 4詳細設計テキストのみを対象にレビュー。
- Unverified: 実ファイルgrep、`git log -S`、pytest、ruff、mypy、smoke実行は未確認。
- Verified: 相関・因果claimはなく、C3/C7の追加論点はなし。

**Facts**
- §2 / §8.4 のdual-path skip契約は、`sidecar_inputs is None` SSOTへ統一済み。
- disabled modeの文言は「iterateは走る、canonical計算のみskip」に修正済み。
- memory gateは`sampled_max_worker_rss < 3 GB`を主条件に格上げされ、元制約との対応は改善済み。

**Interpretations**
- Alpha Factory本体の設計はAPPROVE水準。
- 反証が残るのは施策6のsmoke運用設計。`psutil`依存・helper追加・docs/scripts波及が§11に反映されておらず、転記漏れパターンとしてまだ危険。

---

## 施策別判定

**施策1: `_PairSidecarInputs`追加**
- 判定: **APPROVE**
- `BrokerTrade` / `Decimal` import波及は明記済み。mypy確認も設計に入っており十分。

**施策2: `_log_canonical_dual_path`拡張**
- 判定: **APPROVE**
- `pair_label`契約は十分に厳密。non-C stageでの拒否も名前空間汚染防止として妥当。

**施策3: `_run_pair_sharpe` 3-tuple化**
- 判定: **APPROVE**
- `metric_unavailable`を観測対象、exceptionのみskipに分離した設計は整合している。

**施策4: `evaluate_cross_pair` sidecar集約**
- 判定: **APPROVE**
- aggregation経路とsidecar経路の分離は明確。metrics汚染リスクも低い。

**施策5: `evaluate_stage_c` dual-path + sanitize**
- 判定: **APPROVE**
- `try...finally` sanitize、disabled mode、invalid pair key skipの契約は整合済み。
- sanitize後のpayload / IPC / archive非漏洩もtest #17で固定される設計。

**施策6: テスト + smoke**
- 判定: **REQUEST_CHANGES**
- [Warning] `psutil` samplingを主指標にするなら、`psutil`が既存依存か新規dev依存かを§11/実装波及に明記する必要がある。
- 修正案: `pyproject.toml`へのdev依存追加、またはstdlib/`ps`ベース実装にする方針を明記。
- [Warning] §11.1必要変更に`scripts/smoke/measure_step1.8_memory.sh`、`scripts/smoke/sample_worker_rss.py`、`scripts/smoke/aggregate_step1.8_memory.py`が入っていない。
- 修正案: smoke関連3ファイルを§11.1へ追加し、test/validation対象にも入れる。
- [Warning] §11.2の「不要な変更」に`docs/alpha_factory/stage-gates.md`がありつつ「必須」と書かれている。
- 修正案: `docs/alpha_factory/stage-gates.md`は§11.1へ移動。`docs/alpha_factory/cross-pair.md`は任意なら§11.2に残す。
- [Warning] psutil sampling失敗時に「B2補助条件のみで暫定運用」とすると、`sampled_max_worker_rss < 3 GB` SSOTが崩れる。
- 修正案: sampling失敗時はB2を`INCONCLUSIVE`としてmerge不可、または明示的な手動worker RSS確認を必須にする。

---

## 横断判定
- ルックアヘッドバイアス: **APPROVE**。
- メモリ制約: **REQUEST_CHANGES**。主条件は妥当だが、sampling失敗時の扱いと依存波及が未固定。
- パフォーマンス: **APPROVE_WITH_MEASUREMENT**。B3 smoke gateで確認する設計は妥当。
- C1/C2: **INCONCLUSIVE**。設計書上のgrep痕跡はあるが、レビュー側では実確認していない。

**全体判定: CHANGES_REQUESTED**

本体設計は承認可能です。残る差し戻し理由は施策6の運用・波及管理のみです。特に`psutil`依存、smoke helper追加、`docs/stage-gates.md`必須更新を§11に接続すれば、Round 5ではAPPROVEDにできる水準です。