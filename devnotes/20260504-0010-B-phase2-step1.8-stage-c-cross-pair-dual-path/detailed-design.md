# 詳細設計: B Phase 2 切替コミット step 1.8 — Stage C cross_pair (ii-lite) dual-path 拡張

**作成日時**: 2026-05-04 00:55 JST (Round 2 改訂: 2026-05-04 01:08 JST、 Round 3 改訂: 2026-05-04 01:18 JST、 Round 4 改訂: 2026-05-04 01:28 JST、 Round 5 改訂: 2026-05-04 01:38 JST、 Round 5 Suggestion 反映 patch: 2026-05-04 01:46 JST)
**status**: **詳細設計 Round 5 APPROVED** (= Codex Round 1-5 全反映、 全 6 施策 APPROVE、 横断判定 APPROVE / APPROVE_WITH_MEASUREMENT、 実装フェーズへ進行可)
**概念設計**: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/conceptual-design.md` (Codex Round 3 APPROVED、 案 A' 採用、 sanitize / pickle / 循環依存 解消済)

---

## 0. 改訂対応マトリクス

### 0.-3 Round 5 APPROVED + Suggestion 2 件 反映 (= 実装注記)

| Round 5 Suggestion | 対応 (= 実装時注記、 設計には影響しない実装ガイダンス) |
|---|---|
| 施策 6 [Suggestion] `sample_worker_rss.py` の `--target-cmdline` 文字列が sampler 自身の cmdline にも含まれる、 自プロセス PID 除外と対象 root process 判定を実装時に明示 | 実装時 `sample_worker_rss.py` で `os.getpid()` で自身の PID を除外、 対象 root process は `cmdline` 一致の最も早く起動した process を root とし、 その descendants を sample 対象とする方針 (= 詳細実装で対応、 § 11.1 の sample_worker_rss.py 仕様に反映予定) |
| 施策 6 [Suggestion] test #26 は「helper が None を返す」 検証と「log が canonical_skipped を emit する」 検証を分けると責務が明確 | test #26 を 2 ケースに分割: #26a = `test_try_evaluate_canonical_five_safe_returns_none_for_no_trade_input`、 #26b = `test_log_canonical_dual_path_emits_canonical_skipped_event_when_canonical_is_none` (= helper 単体の責務分離、 実装時に test 名を SSOT) |

### 0.-2 Round 4 → Round 5 改訂対応マトリクス

| Round 4 指摘 | 対応 |
|---|---|
| 施策 6 [Warning] psutil sampling 主指標なら psutil が既存依存か新規 dev 依存か明記必要 | **psutil>=5.9 は既存依存** (= `pyproject.toml:22` 確認済、 stdlib 経由ではなく既存依存をそのまま再利用)。 § 11.1 に明記 |
| 施策 6 [Warning] § 11.1 必要変更に smoke 関連ファイル不在 | § 11.1 に `scripts/smoke/measure_step1.8_memory.sh` / `scripts/smoke/sample_worker_rss.py` / `scripts/smoke/aggregate_step1.8_memory.py` の 3 ファイルを追加 (= 新規追加対象、 acceptance B2/B3 merge 条件の SSOT) |
| 施策 6 [Warning] § 11.2 不要な変更に `docs/alpha_factory/stage-gates.md` ありつつ「必須」 と矛盾 | `docs/alpha_factory/stage-gates.md` を § 11.1 必要変更に **移動**、 § 4.7 ログ命名規約 SSOT 拡張 (= `C_cross_pair` + `pair_label` の追記) を必須として明示。 `docs/alpha_factory/cross-pair.md` は任意のため § 11.2 に残す |
| 施策 6 [Warning] psutil sampling 失敗時 B2 を「補助条件のみ暫定運用」 とすると SSOT が崩れる | sampling 失敗時は **B2 を INCONCLUSIVE として merge 不可** (= 主条件 SSOT を維持)、 fallback 経路 (= `ps -o rss= -p` 等の手動確認 SSOT 経路) を § 12.4 に明記、 段階フォールバックではなく SSOT 維持を優先 |

### 0.-1 Round 3 → Round 4 改訂対応マトリクス

| Round 3 指摘 | 対応 |
|---|---|
| 施策 5 [Warning] § 8.4 コードコメントに古い文言「disabled mode 軽量分岐 (= per-pair iterate を skip、軽量 log のみ emit」 が残っており実装者が誤読する | コメントを「per-pair iterate は走るが canonical 計算のみ skip、 軽量 log を emit」 に統一 |
| 施策 5 [Warning] § 2 概念設計リファレンスに「pair_failure pair で dual_path emit されない」 の古い契約が残り Round 3 SSOT と衝突 | § 2 を「`sidecar_inputs is None` の pair のみ emit しない。 metric_unavailable は canonical_skipped emit 対象」 に更新 |
| 施策 6 [Warning] § 12.3 の B2 判定が `process_tree_peak_rss < 24GB` で元制約 (= 6 worker / 1 worker 約 3GB) の直接検証ではない | merge gate を **`process_tree_peak_rss < 18 GB`** (= 6 worker × 3 GB の総量上限、 暫定) + 可能なら psutil による worker 別 RSS 計測 (= `max_worker_rss < 3 GB` が本来の B2、 集計 helper 拡張で対応) に強化 |
| 施策 6 [Warning] `/usr/bin/time -l` の `maximum resident set size` の解釈は macOS/BSD で要確認 | 指標説明を「time -l 由来の参考 RSS (= macOS では process group max RSS の挙動が BSD-compatible で必ずしも合計ではない)」 に弱める。 集計 helper では補足として psutil で per-worker RSS を計測する経路を追加 |
| 施策 1 [Suggestion] BrokerTrade import 元は実装時に型実体と一致確認が必要 | § 4.2 波及変更に「実装時 `from src.broker.orders import Trade as BrokerTrade` の既存 alias と一致するか mypy で確認」 を追記 |
| 施策 2 [Suggestion] エラーメッセージが長いため test では主要部分一致のほうが保守しやすい | test #28 / test #29 の assert は `pytest.raises(ValueError, match="C_cross_pair")` 等の主要部分一致で記述 (= 全文一致は保守困難) |

### 0.0 Round 2 → Round 3 改訂対応マトリクス

| Round 2 指摘 | 対応 |
|---|---|
| 施策 1 [Warning] `BrokerTrade` / `Decimal` import 波及が設計に明記されていない | § 4.2 波及変更に「stage_gate.py の type import 追加 (= `BrokerTrade`, `Decimal`、 既存 import の有無を確認後追加)」 を明記 |
| 施策 1 [Suggestion] E7 は将来 mutation 防止までは保証しない、 test 名は「現行 dual-path が mutation しない」 に寄せる | test #19 名を `test_pair_sidecar_inputs_content_unchanged_through_current_dual_path_emit` に修正 (= 「現行」 を明示) |
| 施策 2 [Warning] `pair_label=" EUR_USD "` (前後空白) は通る、 実 pair 名契約なら拒否すべき | `pair_label != pair_label.strip()` も ValueError raise (= 前後空白混入も識別子契約違反、 § 5.4 修正) |
| 施策 2 [Suggestion] `stage_label != "C_cross_pair"` で `pair_label is not None` なら拒否、 ログ名前空間汚染防止 | 識別子契約 SSOT に「C_cross_pair 以外で pair_label 指定は ValueError」 を追加 (= § 5.4 修正、 acceptance D5 拡張) |
| 施策 3 [Warning] `metric_unavailable` を sidecar 保持に変えたため「pair_failure pair skip」 契約と矛盾 | 契約整理: **exception pair のみ dual-path skip**、 **metric_unavailable は canonical_skipped emit 対象**。 acceptance C6 / test #4 名を更新、 SSOT を「`sidecar_inputs is None` が dual-path skip の唯一条件」 に統一 |
| 施策 3 [Warning] `_try_evaluate_canonical_five_safe` が no-trade で必ず None を返す前提が未検証 | 新規単体 test (= test #26) で no-trade / metric_unavailable 入力 で `canonical_skipped=True` event emit を固定 |
| 施策 4 [Warning] `pair_failures` に metric_unavailable が入る一方 sidecar 保持で test と衝突しやすい | SSOT 明記: 「`sidecar_inputs is None` が dual-path skip の真の条件、 `pair_failures` リストは既存 cross_pair gate 用で dual-path 配線とは独立」 (= § 7.4 設計判断に追記、 acceptance C6 名前を「pair-level skip 整合 (= sidecar_inputs is None で skip)」 に修正) |
| 施策 5 [Warning] disabled mode 説明「per-pair iterate 全体を skip」 と実コード「iterate するが log のみ」 が矛盾 | 文言統一: 「canonical 計算のみ skip、 per-pair lightweight log は emit」 に修正 (= § 8.4 説明と実コード一致) |
| 施策 5 [Suggestion] invalid pair key で `_log_canonical_dual_path` 未到達も test #25 で固定 | test #25 に「invalid pair key 時 `_log_canonical_dual_path` が呼ばれないこと」 monkeypatch 検証を追加 |
| 施策 6 [Warning] test #4 が metric_unavailable まで含むか曖昧 | test #4 を「`exception pair skips dual-path`」 に限定、 別テスト #27 「`metric_unavailable pair emits canonical_skipped event with bt`」 を分離追加 |
| 施策 6 [Warning] smoke script が `python3` 直呼び、 uv 必須ルールと不整合 | `uv run python scripts/smoke/aggregate_step1.8_memory.py` に変更 (= § 12.3 修正) |
| 施策 6 [Warning] `/usr/bin/time -l` で `peak_rss_max_per_worker` を正確に出せるか不明 | 指標名を `process_tree_peak_rss` (= /usr/bin/time -l が出すのは process tree 全体の peak RSS) に変更、 worker 別 RSS は別途 `psutil` 等で取得する旨を § 12.3 に追記 |

### 0.1 Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 |
|---|---|
| 施策 2 [Critical] `pair_label` fail-fast が `None` のみ、 空文字/空白を通す。 識別子契約不完全 | `not isinstance(pair_label, str) or not pair_label.strip()` の場合も ValueError raise (= 識別子契約厳密化、 § 5.4 / acceptance D5 強化) |
| 施策 5 [Critical] sanitize は条件付きで `finally` 保証ではない。 「常時 sanitize」 契約に対して脆い | dual-path 全体を `try ... finally` 化、 sanitize は finally 句で常時実行 (= CrossPairResult なら常に `replace(..., _shadow_sidecar_inputs={})`、 § 8.4 / acceptance E2 強化) |
| 施策 1 [Warning] frozen でも list/dict は可変、 後段変更で観測値が変わる余地 | sidecar の bars / trades / equity_curve は cross_pair.py / stage_gate.py 内で write しない契約 (= 不変前提)、 acceptance E に「sidecar field 内容が dual-path log emit 後に変化していないことを deep equality 比較」 追加 (= test #19 で固定)。 tuple 化は型違反 (= run_backtest が list を返す既存 API) のため見送り |
| 施策 1 [Suggestion] private 型を他 module から import する契約を docstring に明記 | `_PairSidecarInputs` docstring に「cross_pair.py から `from src.alpha_factory.stage_gate import _PairSidecarInputs` 単方向 import で参照する契約」 を明記 (= § 4.4 docstring 拡張) |
| 施策 2 [Warning] 51 caller 後方互換は実測未提示 | helper 単体 test で全 stage ラベル (= A / B_IS / B_fold / C_base / C_stress) の互換ケース 5 本を新規追加 (= test #20-24、 既存 51 caller の動作不変を helper 単体で固定) |
| 施策 3 [Warning] `metric_unavailable` で sidecar 捨てる設計は 3 entries/genome 目標と衝突し得る | `metric_unavailable` でも sidecar (= bars / trades / equity_curve / bt) は保持する設計に変更。 `bt.trade_sharpe_raw is None` でも bt は valid (= compute_metrics 成功)、 canonical_five 計算自体は呼んでも no-raise 契約 + 内部 fallback で None 返り、 dual_path event は `canonical_skipped=True` で emit (= 観測価値: trade なし genome の per-pair canonical 状態が観測可能、 § 6.4 改訂) |
| 施策 3 [Warning] メモリ影響を `N/A` 扱いは不正確 (= trades/equity/bars 保持が増える) | § 12 にワーカー当たり上限見積り表を新設 (= base ~200 MB / step 1.5/1.7 同等規模 + sidecar ~22 MB / genome short-lived peak)、 超過時は target のみ縮退案を別 step で再設計 |
| 施策 4 [Warning] `bars=list(pair_bars[pair])` を 3 ペア分保持、 ピーク RSS 増 | `run_backtest` の bars 入力は非破壊 (= 既存実装で確認済)。 ただし shallow copy の既存挙動は保持 (= 既存 caller との互換性、 概念設計 § 2.1 と整合)。 メモリ実測 § 12 で確証 |
| 施策 4 [Suggestion] 既存集約経路非干渉を固定する回帰 test 強化 | test #16 を強化、 全 metrics keys (= sharpe_per_pair / mean_sharpe / std_sharpe / min_sharpe / aggregate_fitness / aggregator_lambda / sharpe_target_single / sharpe_target_cross / sharpe_target_cross_ratio / liquidity_weighted_mean / pass_criteria / skipped / skip_reason / mode) の deep equality 比較を test に明示 |
| 施策 5 [Warning] disabled mode でも per-pair で重い経路に入る設計余地 | disabled mode (= `phase2_canonical_metrics_mode == "disabled"`) のとき、 per-pair iterate 全体を skip し、 軽量 log (= per-pair `canonical_skipped=True` 1 行 / pair) のみ emit する分岐を追加 (= § 8.4 改訂、 step 1.6 disabled mode と整合) |
| 施策 5 [Warning] `pair` キー値の妥当性検証なし | dual-path ループ内で `pair` が空文字 / 空白なら `logger.warning` + skip (= 内部不整合の早期検出、 § 8.4 改訂) |
| 施策 6 [Warning] B2/B3 (= メモリ予算) を merge gate にするなら自動計測スモーク 1 本必要 | 新規 smoke スクリプト `scripts/smoke/measure_step1.8_memory.sh` を別 git-tracked 配置、 詳細設計 § 12.3 で実測手順を SSOT 化 (= acceptance B2 merge 条件の運用化) |
| 施策 6 [Warning] `parallel_eval._extract_cross_pair_result` 経由の sanitize 非漏洩 統合 test 不足 | test #17 を強化、 `evaluate_stage_c → cross_pair_payload → _extract_cross_pair_result → GenomeStageResult.cross_pair` の E2E 経路で `_shadow_sidecar_inputs == {}` を deep equality 比較 (= acceptance E6 強化) |
| 横断 メモリ制約 INCONCLUSIVE | § 12 ワーカー当たり上限見積り表 + smoke スクリプト で実測証跡を Round 2 で揃える (= merge 条件) |
| 横断 パフォーマンス REQUEST_CHANGES (= canonical 追加 3 回分の影響見積り不足) | § 12.4 に enabled mode の per-genome wall time 増分見積り表を追加 (= step 1.7 比 +3x canonical 計算、 disabled mode は overhead 0)、 acceptance B3 の閾値判断を smoke 実測で固定 |
| 横断 C1/C2 INCONCLUSIVE | § 14 参考資料に「Round 1 で実施した着手前調査の grep 痕跡」 を明示追加 (= `_run_pair_sharpe` caller 全件 / cp_inputs 構築経路 / archive transport 経路、 概念設計 § 9.4 と整合) |

---

## 1. 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間延長
2. 数値見せかけ改善
3. GA ハック
4. live_criteria 緩和
5. **過度な複雑化** ← 本 step で特に重要 (= cross_pair.py 改修を sidecar 保持・返却のみに最小化)
6. 取引回数削減
7. オーバーナイト保有前提
8. ゲノム archive スキーマ変更時の値伝搬漏れ

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞い説明的、 汎用的
- テスト配置: 対象モジュール対応のテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過

---

## 2. 概念設計リファレンス

`devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/conceptual-design.md` (Round 3 APPROVED)

主要決定:
- **採用案**: A' (= cross_pair.py は sidecar 保持・返却のみ、 canonical 計算と log emit は stage_gate.py 側、 責務境界明確化)
- **scope**: Stage C cross_pair 区画 (= ii-lite shadow 評価) で per-pair canonical 5 軸を descriptive 観測 (= 3 entries / genome、 mission 必須軸の observability 完成)
- **descriptive observation only**: cross_pair gate (= aggregate_fitness / mean_sharpe / sharpe_ratio / min_sharpe) の shadow ではない、 per-pair canonical はいわば「ii-lite gate の constituent observability」、 cross-pair diff は dual-path log entry に含まれない
- **`_PairSidecarInputs` 配置**: stage_gate.py 側の CrossPairResult 近傍に定義 (= cross_pair.py からの単方向 import 経路維持、 循環依存回避)
- **`CrossPairResult._shadow_sidecar_inputs` field**: `dict[str, _PairSidecarInputs] = field(default_factory=dict, repr=False, compare=False)` (= multiprocessing pickle 互換、 repr / equality 除外)
- **物理隔離**: dual-path 配線は stage_gate.py 側の cp_result 受け取り後・cross_pair_payload 確定後の **別 try ブロック**、 cross_pair_payload / cp_result.metrics / sharpe_per_pair / pair_failures / pass_criteria に絶対干渉しない
- **sanitize 経路**: canonical log 後、 dual-path 経路の例外有無 / disabled mode / sidecar 空にかかわらず常に `cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})` で sidecar を空 dict に差し替え (= payload / IPC / archive に sidecar 漏れない契約)
- **skip 整合 (= dual-path skip SSOT)**: `cross_pair_payload["skipped"] is True` / `cp_result is None` / `_shadow_sidecar_inputs` が空 / **`sidecar_inputs is None` の pair (= exception pair)** で dual_path / canonical_five.skipped event 両者 emit されない。 metric_unavailable pair (= bt 計算成功 + trade_sharpe_raw None) は **sidecar 保持で dual-path 経路に進み、 `canonical_skipped=True` event emit 対象** (= Codex detailed-review Round 3 [Warning 施策 5] 反映で SSOT 統一、 § 0.-1 Round 3 → Round 4 改訂対応参照)
- **disabled mode**: cross_pair 成功時のみ canonical_skipped=True の dual_path event emit (= step 1.6 B_fold と同型)
- **identifier 契約**: `(stage="C_cross_pair", genome=<genome.name>, pair=<実 pair 名>)` の 3 つで一意特定 (= 1 entry / pair / genome、 計 3 entries / genome / Stage C)
- **acceptance**: A (判定結果回帰 0) + B (運用回帰検証 + B2 merge 条件) + C (legacy 比較可能性 + 識別子契約) + D (例外隔離契約) + E (名前空間隔離 + multiprocessing pickle + sanitize)

---

## 3. 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|---|---|---|
| 1 | `_PairSidecarInputs` 新規定義 + `CrossPairResult._shadow_sidecar_inputs` field 追加 | src/alpha_factory/stage_gate.py | High |
| 2 | `_log_canonical_dual_path` 拡張 (= `pair_label` 追加 + C_cross_pair 識別子契約 fail-fast + docstring 更新) | src/alpha_factory/stage_gate.py | High |
| 3 | `cross_pair.py` の `_run_pair_sharpe` 戻り値 3-tuple 化 (= sidecar_inputs 追加) | src/alpha_factory/cross_pair.py | High |
| 4 | `cross_pair.py` の `evaluate_cross_pair` で sidecar 集約 → `CrossPairResult` 渡し | src/alpha_factory/cross_pair.py | High |
| 5 | `evaluate_stage_c` cross_pair 区画 dual-path 配線追加 (= 別 try、 物理隔離) + sanitize 経路 | src/alpha_factory/stage_gate.py | High |
| 6 | C_cross_pair dual-path test 追加 + 既存 51 ケース後方互換確認 | tests/alpha_factory/test_stage_gate_canonical_dual_path.py and/or test_cross_pair*.py | High |

---

## 4. 施策 1: `_PairSidecarInputs` + `CrossPairResult._shadow_sidecar_inputs` field

### 4.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py` (= `CrossPairResult` dataclass 定義 L544-559 の近傍)

### 4.2 波及変更
- `cross_pair.py` 側 import 追加 (= 施策 3 で対応): `from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs`
- **`stage_gate.py` 側 type import 追加** (= Round 2 [Warning 施策 1] 反映、 _PairSidecarInputs の field 型として使用):
  - `BrokerTrade`: `from src.broker.orders import Trade as BrokerTrade` (= cross_pair.py で同一 alias を使っており、 stage_gate.py 既存 import の有無を実装時に確認、 不在なら追加。 Round 3 [Suggestion 施策 1] 反映で実装時に mypy で型実体一致 (= cross_pair.py と同 alias) を確認)
  - `Decimal`: `from decimal import Decimal` (= 既存 import の有無を実装時に確認、 不在なら追加)
  - `BacktestMetrics`: 既存 import あり (= step 1.5 / 1.6 / 1.7 で使用済)
  - `PriceBar`: 既存 import あり (= step 1.5 / 1.6 / 1.7 で使用済)
- 既存 `CrossPairResult(target_pair=..., anchor_pairs=..., aggregator_name=..., window=..., passed=..., metrics=..., reason_codes=...)` callers (= positional / keyword) は **完全に backward-compatible** (= 新規 field は default factory)

### 4.3 現行コード (step 1.7 後)

```python
@dataclass(frozen=True)
class CrossPairResult:
    """cross-pair (ii-lite) 評価の戻り値。
    ..."""
    target_pair: str
    anchor_pairs: tuple[str, ...]
    aggregator_name: str
    window: tuple[datetime, datetime]
    passed: bool
    metrics: Mapping[str, object]
    reason_codes: tuple[str, ...] = ()
```

### 4.4 変更後コード

```python
# (CrossPairResult の直前、 同 module 内)
@dataclass(frozen=True)
class _PairSidecarInputs:
    """canonical_five 計算用 input 集合 (= dual-path 経路でのみ使用).

    ``cross_pair.py`` で per-pair backtest 結果 (= trades / equity_curve / bt) を
    保持し、 ``stage_gate.py`` 側 dual-path 配線で canonical 5 軸を計算する際に
    使う ephemeral 入力集合。 deep copy なし、 既存経路の shallow copy
    (例: ``bars=list(pair_bars[pair])``) を許容。 canonical 計算後、
    ``CrossPairResult._shadow_sidecar_inputs`` の sanitize (= 空 dict 差し替え)
    で payload / IPC / archive に絶対漏れない契約 (= 概念設計 § 2.4 / acceptance E)。

    本 dataclass は ``stage_gate.py`` 側に定義することで、 ``cross_pair.py`` から
    の単方向 import 経路を維持し循環依存を回避する (= 概念設計 Round 2
    [Critical 3] 反映)。

    Import 契約 (= Codex detailed-review Round 1 [Suggestion 施策 1] 反映):
        ``cross_pair.py`` からは ``from src.alpha_factory.stage_gate import
        CrossPairResult, _PairSidecarInputs`` で参照する。
        - cross_pair.py → stage_gate.py の単方向 import (= 既存配線維持)
        - stage_gate.py → cross_pair.py の逆 import は禁止 (= 循環依存 防止)
        - 他 module からの import は想定しない (= leading underscore で
          module-private を明示)

    不変前提 (= Codex detailed-review Round 1 [Warning 施策 1] 反映):
        bars / trades / equity_curve は production code (= cross_pair.py /
        stage_gate.py / canonical_adapter.py / canonical_metrics) で書き込まれない
        契約。 sidecar 構築から sanitize 完了までの間、 内容は不変
        (= acceptance E7 で deep equality 比較で固定)。 frozen=True dataclass で
        attr 再代入は防げるが、 list / dict は技術的に mutable のため、 production
        code の振る舞い契約として明文化する。
    """
    bars: list[PriceBar]
    trades: list[BrokerTrade]
    equity_curve: list[tuple[datetime, Decimal]]
    bt: BacktestMetrics


@dataclass(frozen=True)
class CrossPairResult:
    """cross-pair (ii-lite) 評価の戻り値。
    ...
    """
    target_pair: str
    anchor_pairs: tuple[str, ...]
    aggregator_name: str
    window: tuple[datetime, datetime]
    passed: bool
    metrics: Mapping[str, object]
    reason_codes: tuple[str, ...] = ()
    # B step 1.8: dual-path 経路用 ephemeral sidecar (= public API ではない、
    # archive / payload transport には漏れない契約、 概念設計 § 2.3)。
    # field 設定:
    #   - default_factory=dict: multiprocessing pickle 互換 (= MappingProxyType 不可、
    #     概念設計 Round 2 [Critical 2])
    #   - repr=False: snapshot 比較ノイズ排除 (= 概念設計 Round 2 [Warning])
    #   - compare=False: dataclass equality から除外 (= acceptance E5)
    _shadow_sidecar_inputs: dict[str, _PairSidecarInputs] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
```

### 4.5 ルックアヘッドバイアスチェック (primitive 変更ではないが念のため)
- [N/A] primitive 変更ではない (= dataclass 定義の追加のみ)

### 4.6 パフォーマンスチェック (primitive 変更ではないが念のため)
- [N/A] primitive 変更ではない

### 4.7 テスト計画

(= 施策 6 にまとめる、 acceptance A2 / E1-E6 対応)

### 4.8 リスク

- `CrossPairResult` の新規 field が dataclass equality / repr に混入 → `compare=False` / `repr=False` で除外契約、 acceptance E5 で固定
- `dict` default が hashable でない → `frozen=True` dataclass + dict field の組合せは Python で許容 (= ハッシュ化は使わない設計、 cross_pair の戻り値は等価比較のみ)
- 既存 `_make_skipped_result` の `CrossPairResult(...)` callers が新規 field を渡さない → default factory で空 dict が入るため backward-compatible

---

## 5. 施策 2: `_log_canonical_dual_path` 拡張

### 5.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:170-257` (= `_log_canonical_dual_path` 関数)

### 5.2 波及変更
- なし (= optional kwarg + None default の追加、 既存 51 caller は keyword 呼出で完全互換)

### 5.3 現行コード (step 1.7 後)

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    Args:
        stage_label: § 4.7 ログ命名規約 SSOT
            (A / B_IS / B_fold / C_base / C_stress / C_cross_pair)。
            注: C_stress は step 1.7 で追加 (= Stage C spread stress backtest)。
        ...
        fold_index: per-fold 識別子 (= 0..n_fold-1)。 stage_label="B_fold" のとき必須、
            他 stage (= A / B_IS / C_base / C_stress / C_cross_pair) は None。
    Raises:
        ValueError: stage_label="B_fold" かつ fold_index is None
    ...
    """
    if stage_label == "B_fold" and fold_index is None:
        raise ValueError(...)

    if canonical is None:
        log_kwargs: dict[str, object] = {
            "stage": stage_label,
            "genome": genome_name,
            "canonical_skipped": True,
        }
        if fold_index is not None:
            log_kwargs["fold"] = fold_index
        logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
        return

    log_kwargs = {
        "stage": stage_label,
        ...
    }
    if fold_index is not None:
        log_kwargs["fold"] = fold_index
    logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
```

### 5.4 変更後コード

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,
    pair_label: str | None = None,  # 新規 step 1.8
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    Args:
        stage_label: § 4.7 ログ命名規約 SSOT
            (A / B_IS / B_fold / C_base / C_stress / C_cross_pair)。
            注: C_stress は step 1.7 で追加、 C_cross_pair は step 1.8 で追加。
        genome_name: genome 識別子 (= logger kwargs key `genome`)。
        legacy: BacktestMetrics (= 既存判定経路、 cross_pair の場合は per-pair `bt`)。
        canonical: CanonicalFiveResult or None (= helper 例外時 / disabled mode)。
        fold_index: per-fold 識別子 (= 0..n_fold-1)。 stage_label="B_fold" のとき必須、
            他 stage (= A / B_IS / C_base / C_stress / C_cross_pair) は None。
        pair_label: per-pair 識別子 (= 実 pair 名、 例 "EUR_USD")。
            stage_label="C_cross_pair" のとき必須、 他 stage (= A / B_IS /
            B_fold / C_base / C_stress) は None。
            step 1.8 で追加 (= 概念設計 § 2.5、 acceptance D5、
            Codex conceptual-review Round 1 [Suggestion] 反映で実 pair 名を採用、
            役割識別 (target / anchor1 / anchor2) は dual-path log に出さず、
            将来 role 分析時は Stage C payload の `target_pair` / `anchor_pairs` と
            `(genome, pair)` で join する設計)。

    Raises:
        ValueError: stage_label="B_fold" かつ fold_index is None
            (= step 1.6 acceptance D5)。
        ValueError: stage_label="C_cross_pair" かつ pair_label is None
            (= step 1.8 acceptance D5、 識別子契約 SSOT、
            C_cross_pair log entry は (stage, genome, pair) で一意特定可能で
            なければならない)。
    ...
    """
    # 識別子契約 SSOT (= step 1.6 + step 1.8)
    if stage_label == "B_fold" and fold_index is None:
        raise ValueError(
            "_log_canonical_dual_path(stage_label='B_fold') requires fold_index ..."
        )
    if stage_label == "C_cross_pair":
        if not isinstance(pair_label, str) or not pair_label.strip():
            raise ValueError(
                "_log_canonical_dual_path(stage_label='C_cross_pair') requires "
                "non-empty pair_label (= step 1.8 acceptance D5 / 識別子契約 SSOT、 "
                "C_cross_pair log entry は (stage, genome, pair) で一意特定可能 "
                "でなければならない、 None / 空文字 / 空白文字列はいずれも "
                "識別子契約違反、 Codex detailed-review Round 1 [Critical 施策 2] 反映)"
            )
        if pair_label != pair_label.strip():
            raise ValueError(
                "_log_canonical_dual_path(stage_label='C_cross_pair') requires "
                "pair_label without leading / trailing whitespace (= step 1.8 "
                "acceptance D5、 実 pair 名契約: 'EUR_USD' は OK、 ' EUR_USD ' は NG、 "
                "Codex detailed-review Round 2 [Warning 施策 2] 反映)"
            )
    elif pair_label is not None:
        raise ValueError(
            f"_log_canonical_dual_path(stage_label={stage_label!r}) does not accept "
            "pair_label (= step 1.8 識別子契約 SSOT、 pair_label は C_cross_pair 専用、 "
            "他 stage で指定するとログ名前空間汚染、 "
            "Codex detailed-review Round 2 [Suggestion 施策 2] 反映)"
        )

    if canonical is None:
        log_kwargs: dict[str, object] = {
            "stage": stage_label,
            "genome": genome_name,
            "canonical_skipped": True,
        }
        if fold_index is not None:
            log_kwargs["fold"] = fold_index
        if pair_label is not None:
            log_kwargs["pair"] = pair_label
        logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
        return

    log_kwargs = {
        "stage": stage_label,
        ...  # 既存 keys
    }
    if fold_index is not None:
        log_kwargs["fold"] = fold_index
    if pair_label is not None:
        log_kwargs["pair"] = pair_label
    logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
```

### 5.5 テスト計画

(= 施策 6 にまとめる、 acceptance C1-C5 / D5 対応)

### 5.6 リスク

- 既存 51 caller (= A / B_IS / B_fold / C_base / C_stress) で `pair_label=None` default が動作不変 → 既存 51 ケース全 PASS で確認 (= 施策 6 / acceptance A5)
- `pair_label is not None` の追加分岐で新規 field 漏れ → log_kwargs に "pair" 追加は 2 箇所 (= canonical None / non-None)、 deep equality test で固定

---

## 6. 施策 3: `cross_pair.py` の `_run_pair_sharpe` 戻り値 3-tuple 化

### 6.1 変更箇所
- ファイル: `src/alpha_factory/cross_pair.py:122-164` (= `_run_pair_sharpe` 関数)

### 6.2 波及変更
- 同ファイル `evaluate_cross_pair` の caller (= L272-280): 戻り値分解代入の拡張 (= 施策 4 で対応)
- import 追加: `from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs` (= 既存 `CrossPairResult` import の追加 import 化)
- `_run_pair_sharpe` は module-private (= leading underscore)、 外部 caller なし (= 概念設計 § 9.4 (a) で確認済)

### 6.3 現行コード (step 1.7 後)

```python
from src.alpha_factory.stage_gate import CrossPairResult  # L36

def _run_pair_sharpe(
    *,
    genome: Genome,
    pair: str,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    trade_count_min_for_sharpe: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> tuple[float, str | None]:
    """単一ペアで backtest 実行し、Sharpe を返す。
    Returns: (sharpe, failure_reason)
    """
    pair_config = replace(backtest_config, instrument=pair)
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, pair_config)
        bt = compute_metrics(
            result.trades,
            result.equity_curve,
            trade_count_min_for_sharpe=trade_count_min_for_sharpe,
        )
        if bt.trade_sharpe_raw is None:
            return 0.0, "metric_unavailable"
        return float(bt.trade_sharpe_raw), None
    except Exception as exc:
        logger.warning(...)
        return 0.0, f"exception:{type(exc).__name__}"
```

### 6.4 変更後コード

```python
from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs  # L36

def _run_pair_sharpe(
    *,
    genome: Genome,
    pair: str,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    trade_count_min_for_sharpe: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> tuple[float, str | None, _PairSidecarInputs | None]:
    """単一ペアで backtest 実行し、Sharpe を返す。

    B step 1.8 で 3-tuple に拡張: 第3要素 ``sidecar_inputs`` は dual-path 経路用の
    canonical_five 計算用 input 集合 (= bars / trades / equity_curve / bt)、
    成功時のみ ``_PairSidecarInputs`` instance、 失敗時 None。
    cross_pair.py 内では参照保持のみ、 canonical 計算は呼ばない (= 案 A' 責務境界、
    概念設計 § 1.4)。

    Returns:
        ``(sharpe, failure_reason, sidecar_inputs)``。
        - 成功時 (= bt 計算成功 + trade_sharpe_raw is not None):
          ``(sharpe, None, _PairSidecarInputs(bars, result.trades,
          result.equity_curve, bt))``
        - metric_unavailable (= bt 計算成功だが trade_sharpe_raw is None):
          ``(0.0, "metric_unavailable", _PairSidecarInputs(...))``
          (= bt は valid、 sidecar 保持で dual-path で canonical 計算 / log emit
          経路に進む。 _try_evaluate_canonical_five_safe の no-raise 契約で
          内部 fallback で None 返り、 dual_path event は canonical_skipped=True
          で emit される、 観測価値: trade なし genome の per-pair canonical 状態が
          観測可能、 Codex detailed-review Round 1 [Warning 施策 3] 反映)
        - exception (= run_backtest / compute_metrics raise):
          ``(0.0, "exception:<Type>", None)``
          (= sidecar 不在、 dual-path skip、 acceptance C6)
    """
    pair_config = replace(backtest_config, instrument=pair)
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, pair_config)
        bt = compute_metrics(
            result.trades,
            result.equity_curve,
            trade_count_min_for_sharpe=trade_count_min_for_sharpe,
        )
        # B step 1.8: bt 計算成功時は sidecar を必ず保持 (= trade_sharpe_raw が
        # None かどうかに依存しない)。 trade_sharpe_raw None 時は metric_unavailable
        # failure_reason を返すが sidecar は保持 (= dual-path で canonical 観測継続)
        sidecar_inputs = _PairSidecarInputs(
            bars=bars,
            trades=result.trades,
            equity_curve=result.equity_curve,
            bt=bt,
        )
        if bt.trade_sharpe_raw is None:
            return 0.0, "metric_unavailable", sidecar_inputs
        return float(bt.trade_sharpe_raw), None, sidecar_inputs
    except Exception as exc:
        logger.warning(
            "cross_pair.pair_failure",
            genome=genome.name,
            pair=pair,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        # exception 時のみ sidecar None (= bt 計算自体に失敗、
        # dual-path で参照すべき bt がない)
        return 0.0, f"exception:{type(exc).__name__}", None
```

**設計判断 (= dual-path skip 条件 SSOT、 Codex detailed-review Round 2 [Warning 施策 3/4] 反映)**:

- `metric_unavailable` (= bt 計算成功だが trade_sharpe_raw None) は **sidecar 保持** (= 観測価値: trade なし genome の per-pair canonical 状態が観測可能)
- **dual-path skip の真の条件は `sidecar_inputs is None`** (= SSOT)
  - exception 時のみ sidecar None で dual-path skip
  - metric_unavailable 時は sidecar 保持 → dual-path 経路で `_try_evaluate_canonical_five_safe` が呼ばれる → no-trade 入力で内部 fallback で None 返り → `_log_canonical_dual_path(canonical=None, pair_label=...)` で **`canonical_skipped=True` event emit** (= 観測継続)
- `pair_failures` リストは **既存 cross_pair gate 用** (= aggregate_fitness / pass_criteria 計算で使用)、 dual-path 配線とは **独立**
  - exception → `pair_failures` 入る + `sidecar_inputs is None` → dual-path skip
  - metric_unavailable → `pair_failures` 入る + `sidecar_inputs is not None` → dual-path emit (= canonical_skipped event)
  - つまり「pair_failures に入っている = dual-path skip」 ではない (= 概念設計 acceptance C6 を「`sidecar_inputs is None` で dual-path skip」 に SSOT 統一、 詳細設計 § 0.0 反映)
- 成功時 / metric_unavailable 時は `_PairSidecarInputs` instance を返す (= bars は caller (= evaluate_cross_pair) が `list(pair_bars[pair])` で渡した参照をそのまま保持、 deep copy なし)
- per-pair backtest が **bt まで計算成功している限り** dual-path 観測は継続 (= 3 entries / genome 目標との整合性、 ただし exception pair は skip で 2 entries 等になる場合あり)

### 6.5 ルックアヘッドバイアスチェック
- [N/A] primitive 変更ではない (= 既存 backtest 結果の参照保持のみ追加)

### 6.6 パフォーマンスチェック
- [N/A] primitive 変更ではない (= sidecar 構築は 1 dataclass instance / pair、 overhead 無視可能)

### 6.7 リスク

- 戻り値型変更 → mypy で他 caller (= 外部 module) への影響を確認 → 概念設計 § 9.4 (a) で「外部 import なし」 確認済、 単一 caller (= evaluate_cross_pair) のみ
- `_PairSidecarInputs` の `bars` field は caller の `bars` 参照そのままを保持 → deep copy なし、 caller の bars が evaluate_cross_pair 内 ループ変数なので、 dict に格納すれば LIFO 解放されない (= sidecar_inputs_per_pair が消えるまで保持)、 メモリ概算 § 4.4 で考慮済

---

## 7. 施策 4: `cross_pair.py` の `evaluate_cross_pair` で sidecar 集約

### 7.1 変更箇所
- ファイル: `src/alpha_factory/cross_pair.py:269-356` (= `evaluate_cross_pair` 内のループ + 戻り値構築)

### 7.2 波及変更
- なし (= sidecar 集約は cross_pair.py 内、 戻り値の `CrossPairResult` constructor に新規 kwarg `_shadow_sidecar_inputs` を渡すだけ)

### 7.3 現行コード (step 1.7 後)

```python
# --- run 3 backtests ---
sharpe_per_pair: dict[str, float] = {}
pair_failures: list[str] = []
for pair in required:
    sh, fail = _run_pair_sharpe(
        genome=genome,
        pair=pair,
        bars=list(pair_bars[pair]),
        meta=pair_meta[pair],
        backtest_config=backtest_config,
        primitive_evaluator=primitive_evaluator,
    )
    sharpe_per_pair[pair] = sh
    if fail is not None:
        pair_failures.append(f"pair_failure:{pair}:{fail}")

# ... aggregation / ratio / pass criteria は完全不変 ...

return CrossPairResult(
    target_pair=target,
    anchor_pairs=(a1, a2),
    aggregator_name=f"mean_minus_{cross_pair_config.aggregator_lambda}_std",
    window=window,
    passed=bool(pc["all"]),
    metrics=metrics,
    reason_codes=tuple(reasons),
)
```

### 7.4 変更後コード

```python
# --- run 3 backtests ---
sharpe_per_pair: dict[str, float] = {}
pair_failures: list[str] = []
sidecar_inputs_per_pair: dict[str, _PairSidecarInputs] = {}  # 新規 step 1.8
for pair in required:
    sh, fail, sidecar_inputs = _run_pair_sharpe(  # 戻り値 3-tuple
        genome=genome,
        pair=pair,
        bars=list(pair_bars[pair]),
        meta=pair_meta[pair],
        backtest_config=backtest_config,
        primitive_evaluator=primitive_evaluator,
    )
    sharpe_per_pair[pair] = sh
    if fail is not None:
        pair_failures.append(f"pair_failure:{pair}:{fail}")
    if sidecar_inputs is not None:
        sidecar_inputs_per_pair[pair] = sidecar_inputs

# ... aggregation / ratio / pass criteria は完全不変 (= sharpe_per_pair / pair_failures
#     / pass_criteria / aggregate_fitness は touch しない) ...

return CrossPairResult(
    target_pair=target,
    anchor_pairs=(a1, a2),
    aggregator_name=f"mean_minus_{cross_pair_config.aggregator_lambda}_std",
    window=window,
    passed=bool(pc["all"]),
    metrics=metrics,
    reason_codes=tuple(reasons),
    _shadow_sidecar_inputs=sidecar_inputs_per_pair,  # 新規 step 1.8
)
```

**設計判断**:
- aggregation / ratio / pass criteria の計算経路は **完全不変** (= 既存 sharpe_per_pair / pair_failures だけ参照)
- `sidecar_inputs_per_pair` は新規変数で集約、 既存 metrics dict / pass_criteria dict には絶対入れない (= 概念設計 [Critical 1] 反映、 metrics 空間を汚染しない)
- `_make_skipped_result` (= cross_pair.py:167-206) は **変更しない** (= 既存 path、 sidecar 不在で skip 経路に直結)、 default factory で空 dict が入る

### 7.5 テスト計画
(= 施策 6 にまとめる、 acceptance A2 / B1 / C5 / C6 対応)

### 7.6 リスク

- aggregation 経路に sidecar が混入 → 計算経路で `sidecar_inputs_per_pair` を一切参照しない (= 戻り値構築時のみ kwarg として渡す)、 acceptance A2 で固定
- `_make_skipped_result` への影響 → 変更なし (= default factory が空 dict を入れる)、 既存 test 全 PASS で確認

---

## 8. 施策 5: `evaluate_stage_c` cross_pair 区画 dual-path 配線 + sanitize

### 8.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:1508-1555` (= `evaluate_stage_c` の cross_pair 区画)
- import 追加: `from dataclasses import replace` (= 既存 stage_gate.py で `replace` を `from dataclasses import dataclass, field, replace` 等で import 済かを実装時に確認、 不在なら追加)

### 8.2 波及変更
- なし (= cross_pair 区画内の追加コード、 既存 `cross_pair_payload` / `cp_result` の判定経路は変更なし)

### 8.3 現行コード (step 1.7 後)

```python
# cross-pair shadow hook (T016)
cross_pair_payload: dict[str, object] = {
    "skipped": True,
    "result": None,
    "error_type": None,
}
if cross_pair_evaluator is not None:
    if cross_pair_inputs is None:
        raise ValueError(...)
    validated = _validate_cross_pair_inputs(cross_pair_inputs)
    cp_result: CrossPairResult | None
    try:
        cp_result = cross_pair_evaluator.evaluate(...)
    except Exception as exc:
        logger.warning("stage_c.cross_pair_failure", ...)
        cp_result = None
        cross_pair_payload["error_type"] = type(exc).__name__
    if cp_result is None:
        cross_pair_payload["skipped"] = True
        cross_pair_payload["result"] = None
    else:
        cp_metrics = cp_result.metrics
        cp_skipped = (
            bool(cp_metrics.get("skipped", False))
            if isinstance(cp_metrics, Mapping)
            else False
        )
        cross_pair_payload["skipped"] = cp_skipped
        cross_pair_payload["result"] = cp_result

passed = len(reasons) == 0
```

### 8.4 変更後コード

```python
# cross-pair shadow hook (T016) — 既存 (完全不変)
cross_pair_payload: dict[str, object] = {
    "skipped": True,
    "result": None,
    "error_type": None,
}
if cross_pair_evaluator is not None:
    if cross_pair_inputs is None:
        raise ValueError(...)
    validated = _validate_cross_pair_inputs(cross_pair_inputs)
    cp_result: CrossPairResult | None
    try:
        cp_result = cross_pair_evaluator.evaluate(...)
    except Exception as exc:
        logger.warning("stage_c.cross_pair_failure", ...)
        cp_result = None
        cross_pair_payload["error_type"] = type(exc).__name__
    if cp_result is None:
        cross_pair_payload["skipped"] = True
        cross_pair_payload["result"] = None
    else:
        cp_metrics = cp_result.metrics
        cp_skipped = (
            bool(cp_metrics.get("skipped", False))
            if isinstance(cp_metrics, Mapping)
            else False
        )
        cross_pair_payload["skipped"] = cp_skipped
        cross_pair_payload["result"] = cp_result

# === B Phase 2 step 1.8: cross_pair dual-path (= 別 try-finally で物理隔離 +
# 常時 sanitize、 acceptance D1-D5 + E1-E6)。 cp_result 受け取り後・
# cross_pair_payload 確定後に走る。 dual-path 経路の例外有無 / disabled mode /
# sidecar 空 / pair_failure / cp_result is None 全分岐で finally 句の sanitize は
# 常時実行される (= Codex detailed-review Round 1 [Critical 施策 5] 反映で
# try-finally に強化) ===
try:
    cp_result_local = cross_pair_payload.get("result")
    if (
        isinstance(cp_result_local, CrossPairResult)
        and not bool(cross_pair_payload["skipped"])
    ):
        sidecar_map: dict[str, _PairSidecarInputs] = (
            getattr(cp_result_local, "_shadow_sidecar_inputs", {}) or {}
        )
        enabled = stage_config.phase2_canonical_metrics_mode != "disabled"
        # disabled mode 軽量分岐 (= per-pair iterate は走るが canonical 計算のみ
        # skip、 lightweight log を emit、 Codex detailed-review Round 1 + Round 3
        # [Warning 施策 5] 反映、 step 1.6 disabled mode と整合)
        if not enabled:
            for pair in sidecar_map.keys():
                if not isinstance(pair, str) or not pair.strip():
                    logger.warning(
                        "stage_gate.canonical_five.invalid_pair_key",
                        stage="C_cross_pair",
                        genome=genome.name,
                        pair=repr(pair),
                    )
                    continue
                try:
                    _log_canonical_dual_path(
                        stage_label="C_cross_pair",
                        genome_name=genome.name,
                        legacy=sidecar_map[pair].bt,  # bt は valid (= sidecar 取得時保証)
                        canonical=None,  # disabled mode → canonical_skipped=True event
                        pair_label=pair,
                    )
                except Exception as log_exc:
                    logger.warning(
                        "stage_gate.canonical_five.log_failed",
                        stage="C_cross_pair",
                        genome=genome.name,
                        pair=pair,
                        error=str(log_exc),
                        error_type=type(log_exc).__name__,
                    )
        else:
            # enabled mode: per-pair canonical 計算 + log emit
            for pair, sidecar in sidecar_map.items():
                # pair キー妥当性検証 (= Codex detailed-review Round 1
                # [Warning 施策 5] 反映、 内部不整合の早期検出)
                if not isinstance(pair, str) or not pair.strip():
                    logger.warning(
                        "stage_gate.canonical_five.invalid_pair_key",
                        stage="C_cross_pair",
                        genome=genome.name,
                        pair=repr(pair),
                    )
                    continue
                try:
                    canonical_sidecar_cp = _try_evaluate_canonical_five_safe(
                        trades=sidecar.trades,
                        equity_curve=sidecar.equity_curve,
                        bars=sidecar.bars,
                        live_criteria=stage_config.live_criteria,
                        window_days=stage_config.stage_c_holdout_days,
                        stage_label="C_cross_pair",
                        genome_name=genome.name,
                        enabled=True,
                    )
                    try:
                        _log_canonical_dual_path(
                            stage_label="C_cross_pair",
                            genome_name=genome.name,
                            legacy=sidecar.bt,
                            canonical=canonical_sidecar_cp,
                            pair_label=pair,
                        )
                    except Exception as log_exc:
                        logger.warning(
                            "stage_gate.canonical_five.log_failed",
                            stage="C_cross_pair",
                            genome=genome.name,
                            pair=pair,
                            error=str(log_exc),
                            error_type=type(log_exc).__name__,
                        )
                except Exception as canonical_exc:
                    logger.warning(
                        "stage_gate.canonical_five.unexpected_failure",
                        stage="C_cross_pair",
                        genome=genome.name,
                        pair=pair,
                        error=str(canonical_exc),
                        error_type=type(canonical_exc).__name__,
                    )
finally:
    # === sanitize 経路 (= sidecar が payload / IPC / archive に絶対漏れない契約、
    # acceptance E1-E6、 概念設計 § 2.4)。 dual-path 経路の例外有無 / 中断 /
    # disabled mode / pair_failure / cp_result is None / skipped 全分岐で常時実行
    # (= Codex detailed-review Round 1 [Critical 施策 5] 反映、 finally 保証) ===
    cp_result_for_sanitize = cross_pair_payload.get("result")
    if isinstance(cp_result_for_sanitize, CrossPairResult) and getattr(
        cp_result_for_sanitize, "_shadow_sidecar_inputs", None
    ):
        cross_pair_payload["result"] = replace(
            cp_result_for_sanitize, _shadow_sidecar_inputs={}
        )

passed = len(reasons) == 0
```

**設計判断**:
- dual-path 配線は **`isinstance(cp_result_local, CrossPairResult) and not skipped`** ガード (= cp_result が None / 古い CrossPairResult instance / skipped 状態では走らない、 acceptance C5)
- `getattr(..., {})` で `_shadow_sidecar_inputs` 不在 (= 古い caller / mock 等) でも crash しない (= backward-compat)
- **disabled mode** (= `phase2_canonical_metrics_mode == "disabled"`、 Codex detailed-review Round 2 [Warning 施策 5] 反映で文言統一):
  - per-pair iterate は **走る** (= sidecar_map.keys() を回す)
  - canonical 計算 (= `_try_evaluate_canonical_five_safe` 呼出) のみ skip
  - per-pair lightweight log (= `_log_canonical_dual_path(canonical=None, pair_label=pair)` で `canonical_skipped=True, pair=<pair>` event) は emit
  - = step 1.6 B_fold disabled mode と同型 pattern
- **enabled mode** のとき:
  - helper が None 返り (= no-trade / metric_unavailable 入力で内部 fallback) → `canonical_skipped=True` event emit
  - canonical 計算成功 → 完全な dual_path event (= legacy_* / canonical_* fields) emit
- **invalid pair key** (= 非 str / 空文字 / 空白) は WARN log + skip (= 内部不整合の早期検出、 `_log_canonical_dual_path` 未到達も test #25 で固定、 Codex detailed-review Round 2 [Suggestion 施策 5] 反映)
- sanitize 経路は dual-path ブロック後の `finally` 句で常時実行 (= 例外時 / disabled mode / sidecar 空 / cp_result is None / pair_failure 全分岐で走る、 Codex detailed-review Round 1 [Critical 施策 5] 反映)
- sanitize 後 `cross_pair_payload["result"]` は sidecar 空 dict の sanitized cp_result、 元の cp_result は GC 対象に

### 8.5 ルックアヘッドバイアスチェック
- [N/A] primitive 変更ではない

### 8.6 パフォーマンスチェック
- [N/A] primitive 変更ではない (= per-pair canonical 計算 3 回追加、 cross_pair 走った場合のみ、 既存 stress canonical 計算と同等オーダー)

### 8.7 テスト計画
(= 施策 6 にまとめる、 acceptance A1 / B1 / B4 / C1-C6 / D1-D5 / E1-E6 対応)

### 8.8 リスク

- sanitize 経路で `cross_pair_payload["result"]` が再取得時に変化 → 並列 access はないため安全 (= evaluate_stage_c は単一スレッド)
- sanitize で `replace(..., _shadow_sidecar_inputs={})` が既存 fields の値を保持 → `replace` の挙動は frozen dataclass で全 fields 保持、 default で None 化されない (= dataclasses module の標準挙動)
- dual-path 配線が disabled mode で走る → `enabled=False` で helper は None 即返り、 `_log_canonical_dual_path(canonical=None, pair_label=pair)` で canonical_skipped event は emit される (= 設計通り、 step 1.6 同型)

---

## 9. 施策 6: テスト追加

### 9.1 変更箇所
- ファイル: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 既存 51 ケース) and/or `tests/alpha_factory/test_cross_pair*.py`
- 既存 51 ケース全 PASS の確認 + 新規 N ケース追加

### 9.2 波及変更
- なし

### 9.3 新規テストケース (= 概念設計 acceptance に対応)

| # | テスト名 (= 振る舞い説明的) | 対応 acceptance | 配置 |
|---|---|---|---|
| 1 | `test_evaluate_stage_c_cross_pair_dual_path_emits_per_pair_logs_in_log_only_mode` | C1, C2, C3, C4, B1, B4 | test_stage_gate_canonical_dual_path.py |
| 2 | `test_evaluate_stage_c_cross_pair_dual_path_skips_when_cross_pair_skipped` | C5 | 同上 |
| 3 | `test_evaluate_stage_c_cross_pair_dual_path_skips_when_cp_evaluator_none` | C5 | 同上 |
| 4 | `test_evaluate_stage_c_cross_pair_dual_path_skips_exception_pair` (= exception pair のみ skip、 metric_unavailable は別 test #27 で扱う、 Round 2 [Warning 施策 6] 反映) | C5, C6 | 同上 |
| 5 | `test_evaluate_stage_c_cross_pair_canonical_failure_isolates_payload` | D1, D3 | 同上 |
| 6 | `test_evaluate_stage_c_cross_pair_log_failure_isolates_payload` | D2, D3 | 同上 |
| 7 | `test_evaluate_stage_c_cross_pair_disabled_mode_emits_canonical_skipped_event` | C5 (disabled mode 分岐 = step 1.6 同型) | 同上 |
| 8 | `test_log_canonical_dual_path_requires_pair_label_for_c_cross_pair` (= None / 空文字 / 空白 全 reject) | D5 | 同上 |
| 9 | `test_evaluate_stage_c_cross_pair_payload_sidecar_is_sanitized_after_dual_path` | E2, E6 (sanitize 経路成功時) | 同上 |
| 10 | `test_evaluate_stage_c_cross_pair_payload_sidecar_is_sanitized_when_canonical_raises` | E2 (sanitize 経路 例外時 finally 保証) | 同上 |
| 11 | `test_evaluate_stage_c_cross_pair_payload_sidecar_is_sanitized_in_disabled_mode` | E2 (sanitize 経路 disabled mode) | 同上 |
| 12 | `test_cross_pair_result_dataclass_compare_excludes_shadow_sidecar` | E5 | test_cross_pair*.py |
| 13 | `test_cross_pair_result_dataclass_repr_excludes_shadow_sidecar` | E5 | 同上 |
| 14 | `test_cross_pair_result_pickle_compatible_with_empty_and_nonempty_sidecar` | E4 | 同上 |
| 15 | `test_evaluate_cross_pair_returns_sidecar_inputs_per_pair_for_successful_pairs` | A2 (cross_pair.py 内 sidecar 集約) | test_cross_pair*.py |
| 16 | `test_evaluate_cross_pair_existing_metrics_keys_unchanged_full_deep_equality` (= 全 metrics keys deep equality 比較強化、 Round 1 [Suggestion 施策 4] 反映) | A2 (既存 public keys 不変) | 同上 |
| 17 | `test_genome_stage_result_extract_cross_pair_does_not_leak_sidecar_e2e` (= evaluate_stage_c → cross_pair_payload → _extract_cross_pair_result → GenomeStageResult.cross_pair の E2E、 Round 1 [Warning 施策 6] 反映) | E1, E6 (archive / IPC transport 経路) | 別ファイル or test_parallel_eval_*.py |
| 18 | `test_evaluate_stage_c_cross_pair_golden_value` | A5 (golden 1 ケース、 step 1.7 と同型) | test_stage_gate_canonical_dual_path.py |
| 19 | `test_pair_sidecar_inputs_content_unchanged_through_current_dual_path_emit` (= 現行 dual-path では sidecar が mutation しないこと、 Round 1 [Warning 施策 1] / Round 2 [Suggestion 施策 1] 反映、 「将来 mutation 防止」 までは保証しない命名) | E7 (sidecar 現行不変) | test_stage_gate_canonical_dual_path.py |
| 20 | `test_log_canonical_dual_path_existing_caller_compat_stage_a` | A5 (helper 単体 stage A 互換、 Round 1 [Warning 施策 2] 反映) | test_stage_gate_canonical_dual_path.py |
| 21 | `test_log_canonical_dual_path_existing_caller_compat_stage_b_is` | A5 (helper 単体 stage B_IS 互換) | 同上 |
| 22 | `test_log_canonical_dual_path_existing_caller_compat_stage_b_fold` | A5 (helper 単体 stage B_fold 互換、 fold_index 必須) | 同上 |
| 23 | `test_log_canonical_dual_path_existing_caller_compat_stage_c_base` | A5 (helper 単体 stage C_base 互換) | 同上 |
| 24 | `test_log_canonical_dual_path_existing_caller_compat_stage_c_stress` | A5 (helper 単体 stage C_stress 互換) | 同上 |
| 25 | `test_evaluate_stage_c_cross_pair_skips_invalid_pair_key_logs_warning_and_does_not_call_log_helper` (= 空文字 / 空白 / 非 str pair key で skip + WARN log + `_log_canonical_dual_path` 未到達 monkeypatch 検証、 Round 1 [Warning 施策 5] / Round 2 [Suggestion 施策 5] 反映) | D5 (内部不整合の早期検出) | 同上 |
| 26 | `test_try_evaluate_canonical_five_safe_returns_none_for_no_trade_input` (= no-trade / metric_unavailable 入力で `canonical_skipped` event emit を helper 単体で固定、 Round 2 [Warning 施策 3] 反映) | C5 / 施策 3 前提検証 | 同上 |
| 27 | `test_evaluate_stage_c_cross_pair_metric_unavailable_pair_emits_canonical_skipped_event_with_legacy_bt` (= metric_unavailable pair で sidecar 保持 + canonical_skipped event emit + legacy_* fields に bt 値が乗ること、 Round 2 [Warning 施策 6] 反映で test #4 から分離) | C5 / 施策 3 / dual-path skip SSOT | 同上 |
| 28 | `test_log_canonical_dual_path_rejects_pair_label_with_leading_or_trailing_whitespace` (= ' EUR_USD ' / 'EUR_USD ' / ' EUR_USD' で ValueError、 Round 2 [Warning 施策 2] 反映) | D5 | 同上 |
| 29 | `test_log_canonical_dual_path_rejects_pair_label_for_non_cross_pair_stages` (= stage_label="A" 等で pair_label 指定で ValueError、 Round 2 [Suggestion 施策 2] 反映) | D5 | 同上 |

### 9.4 既存 51 ケースの後方互換確認

- 既存 stage A / B_IS / B_fold / C_base / C_stress 51 ケース全 PASS (= acceptance A5)
- `_log_canonical_dual_path(pair_label=None)` default で既存 caller は完全互換 (= test #1-51 で確認)

### 9.5 テストヘルパー追加

step 1.6 / 1.7 で確立した capsys ベースの log capture pattern を再利用 (= step 1.7 § 6.4 同型):
- `assert "stage_gate.canonical_five.dual_path" in captured.err`
- `assert "stage='C_cross_pair'" in captured.err`
- `assert "pair='EUR_USD'" in captured.err`
- `assert "stage_gate.canonical_five.skipped" not in captured.err` (= D2 反証 / C5)

### 9.6 実装規模見込み

- 新規 test ~29 ケース (= Round 1 → Round 2 で 18 → 25、 Round 2 → Round 3 で 25 → 29、 metric_unavailable / pair_label 厳密化 / non-C_cross_pair 拒否 / no-trade 単体 を追加)
- 既存 ファイルへの追加: ~900 行 (test, fixture, helper 含む)
- 新規 smoke スクリプト: `scripts/smoke/measure_step1.8_memory.sh` (= acceptance B2 merge 条件、 § 12.3 SSOT)
- mypy / ruff 通過は CI 時間内に収まる見込み

### 9.7 Acceptance E に新規追加 (= Round 1 [Warning 施策 1] 反映)

acceptance E (= 名前空間隔離 + multiprocessing pickle + sanitize) に E7 を追加:

- [E7] **sidecar 不変前提**: `_PairSidecarInputs.bars` / `.trades` / `.equity_curve` / `.bt` の内容が dual-path log emit 前後で変化していないこと (= deep equality 比較で固定、 production code が write しない契約の test 担保、 test #19 で検証)

---

## 10. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** |
| 判断根拠 | 既存 stage_gate / cross_pair / canonical_metrics モジュールの拡張のみ (= 新規モジュール / 大規模 refactor なし)。 step 1.5 / 1.6 / 1.7 と同型の dual-path 拡張で確立済 pattern。 sanitize 経路は新規だが影響範囲は cp_result 1 経路に局所 |
| 競合リスク | 低 (= 他施策との干渉なし、 main flow は単一 worktree todo branch で進める) |
| 想定実装時間 | 中 (= 6 施策、 18 test ケース、 step 1.7 = 8 test より多いが pattern は確立済) |

---

## 11. 波及変更

### 11.1 必要な変更 (= 実装・テスト・運用波及、 Round 4 [Warning 施策 6] 反映で smoke 関連 + docs 必須を追加)

#### コード本体
- `src/alpha_factory/stage_gate.py`: 施策 1 / 2 / 5 (= 主改修)
- `src/alpha_factory/cross_pair.py`: 施策 3 / 4 (= 最小改修)

#### テスト
- `tests/alpha_factory/test_stage_gate_canonical_dual_path.py`: 施策 6 主体 (= 計 25 ケース追加)
- `tests/alpha_factory/test_cross_pair*.py`: 施策 6 一部 (= sidecar / pickle / metrics 不変 etc.)

#### Smoke 計測関連 (= 新規追加、 acceptance B2 / B3 merge 条件 SSOT)
- `scripts/smoke/measure_step1.8_memory.sh` (= smoke 5 Run 起動 + psutil sampling 連携)
- `scripts/smoke/sample_worker_rss.py` (= **既存依存 `psutil>=5.9`** = `pyproject.toml:22` を再利用、 1 秒間隔で per-worker RSS sampling、 `--target-cmdline` で対象プロセス特定)
- `scripts/smoke/aggregate_step1.8_memory.py` (= time -l + sampling JSONL を併合し SSOT 指標 `sampled_max_worker_rss` / 補助指標 `process_tree_rss_max` / `wall_time_mean_per_run` を出力)

#### ドキュメント
- `docs/alpha_factory/stage-gates.md`: § 4.7 ログ命名規約 SSOT に **`C_cross_pair` / `pair_label` を追記 (= 必須)**、 step 1.7 と同型 (= Round 4 [Warning 施策 6] 反映で § 11.2 から 移動)

### 11.2 不要 / 任意 変更 (= 案 A' で伝搬面最小化)

#### 不要 (= 完全不変)
- `AGENTS.md`: 変更なし (= public API 変化なし、 既存運用手順不変)
- `.claude/skills/zenigame-fx-*/SKILL.md`: 変更なし
- `config/alpha_factory/default.yaml`: 変更なし (= `CrossPairConfig` 不変、 stage_config 不変)
- `src/alpha_factory/parallel_eval.py` / `src/alpha_factory/swim_lane.py`: 変更なし (= caller 側の改修不要、 既存 backward-compat)
- `pyproject.toml`: **変更なし** (= psutil>=5.9 は既存依存、 Round 4 [Warning 施策 6] 反映)

#### 任意 (= 望ましいが必須ではない)
- `docs/alpha_factory/cross-pair.md`: dual-path 配線箇所への注記 1 段落追加が望ましい (= 任意、 step 1.7 と同型)

---

## 12. メモリ実測 + パフォーマンス見積り (= acceptance B2 / B3 merge 条件)

### 12.1 ワーカー当たり上限見積り (= Round 1 [Warning 施策 3] 反映、 概念設計 § 4.4 拡張)

| 構成要素 | base step (= step 1.7) | sidecar 保持中 | sanitize 後 |
|---|---|---|---|
| BarEquitySeries / pair (= ~60K bars M1) | ~5-7 MB | ~5-7 MB | 0 MB (= GC 対象) |
| TradeRecord tuple / pair | <0.5 MB | <0.5 MB | 0 MB (= GC 対象) |
| business_day_universe / canonical_five 派生 / pair | <50 KB | <50 KB | 0 MB |
| **per-genome 合計 (3 pairs sidecar 保持時)** | (= 1 pair only) | **~17-22 MB / genome** (= short-lived peak) | 0 MB |
| **per-worker base step (= step 1.7 実測ベース仮設)** | **~200-500 MB** (= step 1.7 実測必要、 概算) | base + ~17-22 MB | base |
| **per-worker step 1.8 RSS 上限見積り** | — | **base + ~22 MB ≪ 3 GB** | base |
| 6 worker 並列 process tree 合計 | base × 6 | (base × 6) + ~100-130 MB | base × 6 |

**結論**:
- per-worker peak RSS 増分は **~22 MB / worker** に局所 (= 3 GB worker budget の 1% 未満、 低リスク仮説)
- process tree 合計増分は **~100-130 MB** (= 24 GB system budget の 1% 未満)
- merge gate (= acceptance B2) は **per-worker max RSS < 3 GB が SSOT**、 process tree 全体も補助的に観測 (= § 12.3 詳細)

### 12.2 パフォーマンス見積り (= Round 1 [Warning パフォーマンス] 反映)

| mode | per-genome canonical 追加計算 | wall time 増分 |
|---|---|---|
| disabled (= phase2_canonical_metrics_mode == "disabled") | 0 (= 軽量分岐で skip、 log のみ) | 0 (= overhead 0) |
| log_only (= default) | 3 calc / cross_pair 走った genome (= step 1.7 比 +3x、 base 1 + stress 1 + cross_pair 3 = 5x の per-genome canonical 計算) | step 1.7 比 +α (= 別 RSS / wall time 計測で確証、 acceptance B3 で ±20% 以内) |

**観測対象**: smoke 5 Run の per-Run wall time、 dual-path log emit count、 peak RSS。 acceptance B3 (= step 1.7 比 ±20% 以内) は smoke 実測で固定。

### 12.3 smoke スクリプト SSOT (= Round 1 [Warning 施策 6] / Round 2 [Warning 施策 6] 反映)

新規 `scripts/smoke/measure_step1.8_memory.sh` (= Round 3 [Warning 施策 6] 反映で psutil sampling 追加):

```bash
#!/bin/bash
# B step 1.8 memory / performance smoke (= acceptance B2 / B3 merge 条件)
# Usage: ./scripts/smoke/measure_step1.8_memory.sh [N_RUNS=5]

set -euo pipefail
N_RUNS=${1:-5}
LOG_DIR="reports/smoke/step1.8"
mkdir -p "$LOG_DIR"

for i in $(seq 1 "$N_RUNS"); do
    # psutil による per-worker RSS sampling を background で開始
    # (= sampled_max_worker_rss SSOT 指標を取得、 acceptance B2 主条件)
    uv run python scripts/smoke/sample_worker_rss.py \
        --output "$LOG_DIR/sample-$i.jsonl" \
        --interval 1.0 \
        --target-cmdline "src.alpha_factory.run_ga" &
    SAMPLER_PID=$!

    # /usr/bin/time -l で参考 RSS / wall time を取得 (= 補助指標)
    /usr/bin/time -l uv run python -m src.alpha_factory.run_ga \
        --config config/alpha_factory/default.yaml \
        --smoke \
        2>&1 | tee "$LOG_DIR/run-$i.log"

    # sampler を停止
    kill "$SAMPLER_PID" 2>/dev/null || true
    wait "$SAMPLER_PID" 2>/dev/null || true
done

# peak RSS / wall time 集計 (= max / mean を計算、 step 1.7 比較)
# Round 2 [Warning 施策 6] 反映: python3 直呼びを uv run python に統一
# Round 3 [Warning 施策 6] 反映: psutil sampling 結果も併合
uv run python scripts/smoke/aggregate_step1.8_memory.py "$LOG_DIR"
```

集計 helper は別途 `scripts/smoke/aggregate_step1.8_memory.py` で実装。

**指標と merge gate (= Round 3 [Warning 施策 6] 反映で強化)**:

`/usr/bin/time -l` の `maximum resident set size` の解釈は macOS / BSD 系で必ずしも process tree 全体の合計 peak とは限らない (= macOS の挙動は OS バージョンに依存、 BSD-compatible でも子プロセス max RSS / 親プロセス RSS を返すケースあり)。 本 step ではこれを **「time -l 由来の参考 RSS」** として弱め、 集計 helper では補足指標として psutil 経由の per-worker RSS も計測する経路を追加する:

```python
# scripts/smoke/aggregate_step1.8_memory.py 抜粋
# /usr/bin/time -l 出力をパース → reference_peak_rss (参考値)
# psutil.Process(pid).children(recursive=True) を smoke 中に sampling
# → sampled_max_worker_rss (= per-worker peak RSS の max、 SSOT)
```

| 指標 | 出所 | 用途 |
|---|---|---|
| `reference_peak_rss_max` | /usr/bin/time -l (= macOS では参考値、 OS 依存挙動あり) | 補助観測 (= merge gate には使わない) |
| `reference_peak_rss_mean` | 同 | 補助観測 |
| `sampled_max_worker_rss` | psutil sampling (= 1秒ごと per-worker RSS 取得 → max を集計、 SSOT) | **merge gate 主指標 (= acceptance B2)** |
| `sampled_process_tree_rss_max` | psutil sampling (= process tree 合計 RSS の max) | 補助観測 |
| `wall_time_mean_per_run` | /usr/bin/time -l (= elapsed time) | merge gate (= acceptance B3) |

**merge gate (= acceptance B2 / B3)**:
- B2 主条件: `sampled_max_worker_rss < 3 GB` (= 元制約 1 worker ≤ 3 GB の直接検証、 SSOT)
- B2 補助条件: `sampled_process_tree_rss_max < 18 GB` (= 6 worker × 3 GB の総量上限、 暫定)
- B3: `wall_time_mean_per_run` が step 1.7 比 ±20% 以内 (= reports/smoke/step1.7/ baseline と比較)

psutil sampling 実装は `scripts/smoke/sample_worker_rss.py` (= **既存依存 `psutil>=5.9`** を再利用、 § 11.1) で integration、 集計 helper から呼ぶ。

**psutil sampling 失敗時の扱い** (= Round 4 [Warning 施策 6] 反映、 SSOT 維持優先):
- psutil が macOS 環境で安定しない場合 (= sampler crash / 0 sample 取得 等):
  - B2 を **INCONCLUSIVE** として merge **不可** (= SSOT 主条件が verify できないため)
  - 暫定運用フォールバックは行わない (= 補助条件のみでの merge 通過を許可しない、 SSOT を崩さない)
- 手動代替経路: `ps -o rss= -p <pid>` で per-worker RSS を実行中に取得し JSONL 化、 `aggregate_step1.8_memory.py` の入力 schema に整合させて手動 SSOT 確認 (= § 12.4)

### 12.4 失敗時のフォールバック (= Round 4 [Warning 施策 6] 反映で SSOT 維持優先)

#### Case A: B2 / B3 が PASS しない場合 (= sampling は成功、 数値が gate 超過)
- step 1.8 を main merge しない
- 縮小案 (= 案 B = target のみ観測、 1 entry/genome) を再設計、 別 step として進める
- ただし mission 軸 partial 観測になるため、 mission completeness は step 2 着手前に再判断

#### Case B: psutil sampling が失敗する場合 (= sampler crash / 0 sample 等、 SSOT verify 不能)
- B2 を **INCONCLUSIVE** として扱う (= SSOT 主条件 `sampled_max_worker_rss < 3 GB` が verify できない以上、 補助条件のみでの merge 通過を許可しない)
- 暫定運用は行わず、 以下のいずれかで SSOT を verify してから merge:
  - 手動 `ps -o rss= -p <pid>` での per-worker RSS 計測 (= 実行中に N sample 取得し JSONL 化、 集計 helper で SSOT 指標を再計算)
  - psutil の動作再現 + 修正 (= macOS バージョン依存の挙動なら別 helper 経路で代替実装)
- B3 (= wall time) は `/usr/bin/time -l` の elapsed time で独立に取得可能なため、 こちらは sampling 失敗の影響を受けない

---

## 13. 残課題・運用観測 follow-up

step 1.7 §残課題に追加:

1. **canonical 失敗件数閾値ベースの fail-fast サーキットブレーカ**: step 1.8 でも WARN log のみ
2. **CI メモリ閾値ガード**: smoke 5 Run の peak RSS / wall time / dual-path log bytes を CI で監視。 step 1.8 では手動実測 (= acceptance B2 merge 条件)
3. **canonical sidecar archive Parquet schema 拡張**: 永続化層への canonical 値書き込み (= step 3 cpps_archive 統合と合わせて検討、 cross_pair の per-pair canonical も対象)
4. **cross_pair gate との対応付け / calibration**: C_cross_pair canonical の意味整合は step 2 か別 step で扱う
5. **stage_bc_evaluator 統合**: step 2 で対応 (= cross_pair 経路の整合は step 1.8 完了後に再確認)
6. **dual-path log volume 増加**: step 1.7 比 +3 entries / genome (cross_pair 走った場合のみ)、 必要なら structlog filter で観測 only run と production run で出力レベル切替

---

## 14. 参考資料

### 14.1 着手前調査の grep 痕跡 (= Round 1 [INCONCLUSIVE C1/C2] 反映、 Round 2 で証跡明示)

概念設計 § 9.4 の Round 2 独立検証成果に加え、 詳細設計 Round 2 で以下の追加調査を実施:

#### (a) `_run_pair_sharpe` caller 全件 (= 概念設計 § 9.4 (a) 確認)
```
grep -rn "_run_pair_sharpe" /Users/ishitoya/repository/zenigame-fx/src --include="*.py"
→ src/alpha_factory/cross_pair.py:122 (definition)
→ src/alpha_factory/cross_pair.py:273 (single caller in evaluate_cross_pair for-loop)
```
外部 module からの import / 呼び出しなし (= module-private な `_` prefix の意図通り)。 戻り値 3-tuple 拡張は単一 caller の改修で完了。

#### (b) `_log_canonical_dual_path` caller 全件 (= step 1.7 後の現状把握)
```
grep -rn "_log_canonical_dual_path" /Users/ishitoya/repository/zenigame-fx/src --include="*.py"
→ src/alpha_factory/stage_gate.py:170 (definition)
→ src/alpha_factory/stage_gate.py:多数 (Stage A / B_IS / B_fold / C_base / C_stress callers)
```
全 caller は keyword 呼出。 新規 optional kwarg `pair_label=None` default で完全 backward-compatible。

#### (c) `cross_pair_payload["result"]` 経由の transport (= 概念設計 § 9.4 (c) 確認)
```
grep -rn "cross_pair_payload\[.result.\]" /Users/ishitoya/repository/zenigame-fx/src --include="*.py"
→ src/alpha_factory/stage_gate.py:1543, 1554 (write)
→ src/alpha_factory/parallel_eval.py:391-396 (_extract_cross_pair_result が読み出し、
  CrossPairResult instance を GenomeStageResult.cross_pair に格納)
→ src/alpha_factory/swim_lane.py: 同型読み出し
```
sanitize 経路が `cross_pair_payload["result"]` の参照を sanitized cp_result に差し替えれば、 `_extract_cross_pair_result` 経由の `GenomeStageResult.cross_pair` も sanitized 版を保持 (= acceptance E6)。

#### (d) `replace` import の確認 (= 施策 5 の依存)
```
grep -n "^from dataclasses" /Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py
→ stage_gate.py 既存 import で確認、 必要に応じて `replace` を追加 import
```

### 14.2 設計ファイル

- 概念設計 (Round 3 APPROVED): `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/conceptual-design.md`
- Codex 概念設計 review Round 1-3: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/conceptual-review-round-{1,2,3}.md`
- Codex 詳細設計 review Round 1 (CHANGES_REQUESTED): `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/detailed-review-round-1.md`
- step 1.7 詳細設計 (Round 2 APPROVED): `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/detailed-design.md`
- step 1.6 詳細設計 (Round 2 APPROVED): `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md`
- step 1.5 詳細設計 (Round 4 APPROVED): `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`
- step 1.7 完了 handoff: `devnotes/20260504-0003-B-step1.7-complete-handoff/handoff.md`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- cross_pair.py (拡張対象): `src/alpha_factory/cross_pair.py:122-356, 364-418`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:170-257 (helper) / 1508-1555 (cross_pair 区画) / CrossPairResult dataclass:544-559`
- 既存 test: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 51 ケース、 step 1.8 で +18 ケース追加予定) and/or `tests/alpha_factory/test_cross_pair*.py`
- docs: `docs/alpha_factory/cross-pair.md` / `docs/alpha_factory/concepts/cross-pair-evaluation-shadow.md` / `docs/alpha_factory/stage-gates.md`
