**本分析の前提**
- `devnotes/20260427-1114-ga-parallel-workers/conceptual-design.md` の提示テキストのみを根拠にしたレビューです。
- `docs/alpha_factory/`、`devnotes/` 関連 T-number、実コード、`git log` は本ターンでは未読です。したがって C1 の「完全 verify」は未達です。
- そのため、`StageResult` 内部フィールド、`archive` / `summary.json` の実スキーマ、cross-pair evaluator の純粋性、Parquet writer の bit 一致性は `未検証` とします。
- Round 1 のため、まず反証を優先して見ています。

**全体判定**
- `CHANGES_REQUESTED`

**Facts**
- 提案の主眼は戦略ロジック変更ではなく、GA 評価の並列化です。
- 設計は「worker は純粋関数」「archive / diagnostics は main process で population 順 collect」を核にしています。
- 成功条件に `max_workers=1` で現行完全同一、`max_workers>1` で archive / summary の決定論的再現可能性を置いています。
- 実装案は `ProcessPoolExecutor` を前提に、worker module-global へ lane context を broadcast する構想です。
- メモリ試算は主に bars 複製を前提にしています。

**Interpretations**
- 方向性自体は使命を妨げません。fitness や gate を歪めないため、禁止事項 2, 3, 4, 6, 7 には直接触れていません。
- ただし、決定論性の主張、worker context 配布の方法、メモリ試算の粒度に設計上の穴があります。
- このままだと「速くなる可能性」はありますが、「bit 一致」「24GB 制約内で安全」はまだ設計として言い切れません。

**観点別レビュー**

1. 使命との整合性
- [Warning] wall-time 短縮は改善サイクルには効きますが、`live_criteria` 達成への寄与は間接的です。設計文の成功条件が速度寄りで、North Star との接続が弱いです。
修正提案: 成功条件に「同一 seed・同一 config で best genome の選好順が不変」「live_criteria 判定結果が worker 数に依存しない」を追加してください。

2. 禁止事項違反
- [Suggestion] 現時点で明示的な違反は見当たりません。A/B/C 期間延長、閾値緩和、取引回数抑制、オーバーナイト化の提案は含まれていません。
- [Suggestion] 「2-3 倍短縮」を前面に出しすぎると、後で速度優先の近道に流れやすいです。速度は副次目標と明記した方が安全です。

3. 実現可能性
- [Critical] `ProcessPoolExecutor` で「世代開始時に各 worker へ lane context を broadcast して module-global に保持」という設計が未具体化です。`initializer` は pool 起動時 1 回で、世代ごとの `_set_lane_ctx` を全 worker に確実に反映する仕組みは本文だけでは成立していません。
修正提案: 次のどちらかに寄せてください。
  1. 各 task に必要 context を明示的に渡す
  2. `multiprocessing.Pool` 前提に戻し、worker 初期化と明示的な context 更新手順を設計に書く
- [Warning] worker 例外を `error: str` で返す案は、traceback やメッセージ内容に runtime 依存情報が混ざると決定論性を壊します。
修正提案: deterministic artifact には `error_code`, `stage`, `genome_name` のような正規化済み構造だけを残し、生 traceback はログ専用に分離してください。

4. 期待効果の妥当性
- [Warning] 「Stage A が wall-time の支配項」という主張は本文内では未計測です。通過率が低いときに効く可能性は高いですが、支配項と断定する根拠はまだありません。
修正提案: 先に `stage_a_seconds`, `stage_b_seconds`, `stage_c_seconds`, `stage_a_pass_rate` を計測対象へ追加し、性能仮説を falsification-first で検証してください。
- [Suggestion] C7 の観点では、単発 1 RUN 比較だけで 2-3 倍短縮を一般化しない方がよいです。少なくとも複数 seed か複数 market condition で観測してください。

5. リスク
- [Critical] bit 一致の主張が強すぎます。population 順 collect だけでは十分ではありません。`summary.json` に wall time, timestamp, warning text, float NaN 表現差、Parquet writer metadata が含まれるなら bit 一致は崩れます。
修正提案: 契約を二段に分けてください。
  - 必須: semantic equivalence
  - 条件付き: bit equivalence
  その上で「bit 一致を保証するために除外すべき非決定 field」を設計に列挙してください。
- [Warning] cross-pair shadow の純粋性は本文上の主張であり、事実確認がありません。pair bar map の内部 cache や logger 副作用があると仮定が崩れます。
修正提案: `cross_pair` 系の副作用禁止を設計前提として明文化し、未達なら `INCONCLUSIVE` に落としてください。

6. スコープ
- [Suggestion] スコープは概ね適切です。SharedBarStore / HistStats を out of scope にしたのも初回実装としては妥当です。
- [Warning] ただし将来差し替えを想定するなら、`parallel_eval` の API を「task transport 層」と「evaluation 層」に分ける設計メモを残した方がよいです。ここを一体化すると後で SharedBarStore 導入時に壊れます。
修正提案: `ParallelEvaluator` の責務境界を 1 段書き足してください。

7. メモリ制約
- [Critical] `~26MB × N` は楽観的です。`list[PriceBar]` は Python object overhead が大きく、spawn 環境では bars 本体、`cp_inputs`, `primitive_evaluator` 補助 dict、`_bars_cache` 展開後データが worker ごとに複製されます。3GB/worker 制約に対する根拠としては不足です。
修正提案: 設計のメモリ節を「raw bars」「Python object overhead」「cross-pair inputs」「derived caches」に分解し、保守的上限で試算してください。既定値は `1` のまま固定し、autopilot 側で自動増加しない方針も明記してください。
- [Warning] 24GB / 6 worker 制約のレビュー観点に対し、「1 machine の GA process が何 worker まで許容か」と「6 worker はシステム全体か GA worker 数か」が本文で曖昧です。
修正提案: 制約対象の単位を明記してください。

8. 前提検証（C4）
- [Warning] 前提が本文中にありますが、`verified` / `unverified` の区別がありません。特に `primitive_evaluator` の pickle 可否、cross-pair 常時 skip、StageResult の純粋性、summary schema の不変性は未検証です。
修正提案: 設計書の前提節を新設し、各項目に `Verified` / `Unverified` / `To measure` を付けてください。

9. Design-first（C1）
- [Warning] 本レビュー時点では docs / devnotes / git 履歴の照合が未実施です。したがって「zenigame との差分が production 制約と整合」という主張はまだ確定できません。
修正提案: 最低でも `run-ga`, `stage-gates`, `swim-lane` の既存 docs と、zenigame 側 parallel 実装の採用理由・撤退理由を追記してください。

10. 決定論性
- [Critical] 「max_workers を変えても archive Parquet が bit 一致」は、現状設計のままでは保証不能です。保証できるのはせいぜい「同一 seed で evaluation result と best selection が一致する」までです。
修正提案: 決定論性の定義を以下に分離してください。
  - Level 1: selection determinism
  - Level 2: row-order determinism
  - Level 3: artifact bit determinism
  そのうえで 이번フェーズの保証対象を Level 1-2 に下げるのが現実的です。

**論点別回答**

1. `worker 副作用なし + population 順 collect` で bit 一致するか
- [Critical] `未証明` です。row 順固定には効きますが、artifact 内の非決定 field を排除した証拠がありません。
修正提案: bit 一致を必須要件から外すか、除外 field と writer 条件を明文化してください。

2. メモリ試算は制約内か
- [Critical] 現状の試算では `未十分` です。Python object overhead と派生 cache が抜けています。
修正提案: 保守的上限試算に更新し、初期 default は必ず `1` を維持してください。

3. Stage A 並列化が支配項か
- [Warning] 仮説としては妥当ですが、現時点では測定不足です。
修正提案: stage 別 timing を先に入れてから speedup claim を書いてください。

4. zenigame 差分の妥当性
- [Suggestion] 初回は妥当です。ただし FX 側でも pair 数や期間が増えると SharedBarStore/HistStats 相当は将来ほぼ必要になります。
修正提案: 今は導入しないが、差し替え可能な境界を残すと明記してください。

5. CLI 名 `--workers` vs `--max-workers`
- [Warning] config 名が `ga.max_workers` なら canonical は `--max-workers` の方が整合的です。`--workers` は alias で十分です。
修正提案: canonical=`--max-workers`、alias=`--workers` を推奨します。

6. `ProcessPoolExecutor` vs `multiprocessing.Pool`
- [Warning] 本文の要件だと、zenigame 既存との整合、initializer、worker context 管理の説明容易性からは `multiprocessing.Pool` の方が自然に見えます。`ProcessPoolExecutor` を選ぶなら、`Future` ベース制御が本当に必要な理由を書くべきです。
修正提案: 今回は `Pool` 優先、`Executor` は明確な利点が立った時だけにした方が設計リスクが低いです。

**総括**
- 方向性は妥当です。使命を汚さず、GA ハックにも当たりません。
- ただし現状の設計文は「決定論性の定義が強すぎる」「worker context 配布方法が未解像」「メモリ試算が楽観的」の 3 点で詰め切れていません。
- 次版では、bit 一致要件の分解、worker context 更新手順の具体化、保守的メモリ上限の再試算を入れてから再レビューに回すべきです。