**前提（本レビュー）**
- `verified`: 提示されたコード断片では、現行は CSV ベース `AuxBundle`（Phase 1）で、`run_ga.py` は `RegistryEvaluator(pair=...)` 単体生成になっている。
- `verified`: `MacroIndexDaily` には現時点で `effective_from_utc` が無い。
- `verified`: 詳細設計は Gate A/B/C の段階導入を前提としている。
- `unverified`: 実運用 DB 方言（PostgreSQL のみか、SQLite も migration 実行対象か）。
- `unverified`: `run_ga` の並列モデル（`fork`/`spawn`）と evaluator インスタンス共有方式。
- `unverified`: `_series_exists_in_period` / `_pair_bars_exist_in_period` の具体実装。
- `unverified`: 空 bars（`len(bars)==0`）が実行上あり得るか。

**C9 Falsification-first（反証先行）**
- 反証試行1: `align_to` は O(N) ではなく O(N*M) ではないか。  
結論: 現設計ループは各 series で pointer 単調前進なので理論上 O(N+M)（設計は妥当）。
- 反証試行2: migration SQL はそのまま安全ではないか。  
結論: `INTERVAL`/`TIMESTAMP WITH TIME ZONE` は SQLite 非互換で、方言依存リスクが残る。
- 反証試行3: preflight の「存在確認だけ」で十分ではないか。  
結論: `effective_from_utc` 契約導入後は「存在」だけだと stale/未有効データを見逃す。
- 反証試行4: Gate C の Warning 0 件基準は hard/soft 分離で矛盾しないのではないか。  
結論: ログ判定基準が hard/soft で明確に分離されない限り運用上の曖昧さが残る。

**施策レビュー（9件）**

1. **施策1 AuxBundle/AlignedAuxBundle**: `REQUEST_CHANGES`  
- [Critical] `align_to` で `bars[-1]` を直接参照しており、空 bars で例外化する。  
修正提案: `if not bars:` で空 `AlignedAuxBundle` を返す契約を先に定義。  
- [Warning] `align_to` を per-genome/per-stage で毎回実行すると総コストが急増する。  
修正提案: stage ごとに 1 回だけ align して evaluator に再利用するキャッシュ層を明記。

2. **施策2 effective_from_utc + migration 004**: `REQUEST_CHANGES`  
- [Critical] backfill SQL が方言依存（SQLite 非互換の可能性高）。  
修正提案: Alembic で方言分岐、または Python update で UTC 明示計算。  
- [Critical] backfill が全 series 一律 +1日で、月次 35日 lag ポリシーと不整合。  
修正提案: series ごとの lag で backfill する（少なくとも既存 series を policy map で分岐）。

3. **施策3 aux_loader DB reader 化**: `APPROVE`  
- [Warning] `-60 days` がマジックナンバー。  
修正提案: `max_policy_lag_days + safety_margin` から導出。

4. **施策4 fetch_fred 拡張**: `REQUEST_CHANGES`  
- [Warning] `ingest/fred.py` から `alpha_factory` 側定数へ依存するとレイヤ汚染。  
修正提案: `effective_from` 計算ロジックを `src/ingest/` 配下の共通モジュールへ移動。  
- [Suggestion] `source` 値（`policy_conservative` vs realtime 起点）の将来拡張方針を先に enum 化。

5. **施策5 aux_pair_bars DB loader**: `APPROVE`  
- [Warning] `datetime` 完全一致 lookup は tz 正規化差で欠番化しやすい。  
修正提案: load 時に UTC 正規化（分解能も M1 に丸める）を契約化。

6. **施策6 events.csv scaffold**: `APPROVE`  
- [Suggestion] partial coverage 前提なので、runbook に「本番判定対象外のイベント欠損」を明記。

7. **施策7 preflight + stage別 evaluator + strict化**: `REQUEST_CHANGES`  
- [Critical] preflight period が Stage B 必要履歴（18ヶ月）を十分表現していない。  
修正提案: `stage_b_start = dataset.start - window_months` を含む期間で hard 判定。  
- [Critical] `_series_exists_in_period` が存在判定のみだと stale を見逃す。  
修正提案: 最低 coverage（例: finite coverage >= X%）と最終有効時刻条件を追加。  
- [Warning] `--allow-aux-missing` と `strict_aux_required=true` の優先順位を明文化すべき。  
修正提案: `CLI > config` かつログに effective strict mode を必ず出力。

8. **施策8 ndarray 化**: `APPROVE`  
- [Suggestion] pickle/multiprocessing 経路の smoke test（1 worker/複数 worker）を追加。

9. **施策9 runbook + wrapper**: `REQUEST_CHANGES`  
- [Critical] `fetch_aux_data.sh` の `--series` 指定が `DGS10,DGS2,T10YIE` を落としており回帰リスク。  
修正提案: DEFAULT_SERIES を使うか、wrapper 側 list を完全同期。  
- [Warning] 失敗時の再実行性（どこで失敗したか）を出力するログを追加。

**全体判定**
- `REQUEST_CHANGES`  
Gate 設計自体は妥当で、Phase 2 の方向性は良いです。  
ただし migration 方言依存、preflight 判定の弱さ、wrapper の series 欠落は本番障害や silent quality 低下に直結するため、先に是正が必要です。

**Fact / Interpretation**
- **Fact**: 提示設計は raw/aligned 分離、effective_from 契約、preflight fail-closed、strict 化までを一貫して定義している。  
- **Interpretation**: 成功確率は高いが、「データ存在=利用可能」とみなす部分と migration 実装の portability を放置すると、Gate C で false pass/false fail が発生する可能性が高い。  

---

**補足（先頭の Numba 設計 7論点のみ簡易判定）**
- 1: `INCONCLUSIVE`（`bars_scale_a=4.29` は妥当寄りだが、Stage A 実バー数ベースで再算定すべき）
- 2: `REQUEST_CHANGES`（`on_bar` 差分 0.69s を dict 由来と断定は早い。内訳計測を追加）
- 3: `REQUEST_CHANGES`（JIT 初回コスト・worker 並列時 compile 戦略を設計に明記）
- 4: `REQUEST_CHANGES`（`fastmath=False` でも bit-identical 保証は過剰。許容誤差契約に変更）
- 5: `INCONCLUSIVE`（`active_clause_indices != 0.0` は微小誤差で変化し得る。再現条件の明文化が必要）
- 6: `INCONCLUSIVE`（Stage B/C 線形効果は方向性は妥当だが、量的主張は未検証）
- 7: `REQUEST_CHANGES`（メモリ見積は楽観的。worst-case signal 数と同時 worker 数で再計算が必要）