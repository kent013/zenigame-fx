**前提検証（C4）**
- 事実: 本レビューは提示された設計文・抜粋コードのみを根拠にしています（実コード未読）。
- 事実: `sharpe_raw/is_full_sharpe` から `trade_sharpe_raw/is_full_trade_sharpe_raw` への移行方針は明記されています。
- 解釈: 主要リスクは「値伝搬漏れ」と「v1/v2 混在時の互換性破綻」です。まず反証（C9）としてこの2点を優先監査しました。

S1 Position/Trade に `equity_at_entry` 追加: **REQUEST_CHANGES**
- [Critical] `Decimal(0)` デフォルトは伝搬漏れを隠します（未設定でも静かに進む）。
修正案: デフォルトを `None` にして、約定生成時に必須チェック（未設定なら例外 or fitness失敗）に変更。
- [Warning] `engine.py` 側の全 `_open_position` 呼び出し（反転・増し玉含む）への引数伝搬が未保証。
修正案: bar先頭で1回取得した `pre_fill_equity` を同barの全open経路で必ず渡す共通経路に統一。

S2 `compute_metrics` に `trade_sharpe_raw` 追加: **REQUEST_CHANGES**
- [Critical] `equity_at_entry<=0` を単純スキップすると選択バイアスが入ります。
修正案: 無効母数が1件でもあれば `trade_sharpe_raw=None` + 理由ログ。
- [Warning] `std == 0` のみ判定は不十分（非有限値考慮不足）。
修正案: `math.isfinite(mean/std)` と `std <= eps` を判定。

S3 GA fitness 切替: **APPROVE**
- [Suggestion] `metric_unavailable` 時に reason code を payload に残すと診断が速い。

S4 Stage Gate 切替: **REQUEST_CHANGES**
- [Critical] key変更は `stage_gate` と `archive.collect_stage_*` の同時反映が必須。片側先行で記録欠損。
修正案: 移行期間は dual-write/dual-read（旧新キー併記）を1リリース入れる。
- [Warning] `trade_count_min_for_sharpe` の引数伝搬が抜ける余地あり。
修正案: `compute_metrics(..., trade_count_min_for_sharpe=...)` を明示渡し。

S5 cross_pair 切替: **REQUEST_CHANGES**
- [Warning] `metric_unavailable` を `0.0` 返却すると真の0と区別不能。
修正案: `None` を返し、呼び出し側で失格扱いに統一。

S6 calibrate_gate 切替: **REQUEST_CHANGES**
- [Warning] v1/v2混在データを同列集計すると閾値校正が崩れます。
修正案: `sharpe_calc_version=="v2_trade_level"` で明示フィルタ、`n<30` は INCONCLUSIVE 扱い（C7/C8）。

S7 Alpha Sieve 切替: **REQUEST_CHANGES**
- [Warning] `trade_count_min_for_sharpe` 未伝搬リスク。
修正案: Sieve内 `compute_metrics` 呼び出しへ明示引数追加。

S8 `run_ga` live_criteria 判定切替: **REQUEST_CHANGES**
- [Critical] 指標の意味が変わるのに既存 `sharpe` 閾値を流用すると不整合。
修正案: `live_criteria.trade_sharpe_raw_min` を新設し、旧設定のみなら起動時エラーで停止。

S9 archive schema + accessor: **REQUEST_CHANGES**
- [Critical] `sharpe_calc_version` を `nullable=False` で追加すると旧データ読込互換が壊れる可能性。
修正案: 一旦 `nullable=True` + 読込時デフォルト補完、移行完了後に厳格化。
- [Critical] 4点セットのうち flush 側（列順/投影）更新が設計記述不足。
修正案: flush出力に新2列が必ず含まれる回帰テストを追加。
- [Warning] `get_trade_sharpe` は `None/non-finite` を明示拒否すべき。
修正案: accessor内で値検証して例外化。

S10 DSRコメント追記: **INCONCLUSIVE**
- [Suggestion] コメントだけでなく「v1/v2比較禁止理由」を関数docstringにも明記すると誤用防止に有効。

S11 config に `trade_count_min_for_sharpe` 追加: **REQUEST_CHANGES**
- [Critical] 4段接続（config→GaConfig→meta→consumer）の設計記述が不足。
修正案: 全段の受け渡し点を明示し、起動時ログ・archiveメタにも記録。
- [Warning] 呼び出し元全網羅（stage_gate/cross_pair/sieve/テスト）が未保証。
修正案: 「新引数未渡しを検出するテスト」を追加。

**テスト計画レビュー（横断）**
- [Critical] 現設計は施策別テストケースが不足。
修正案: 最低限、`key移行互換(旧新)`, `equity_at_entry未設定検知`, `archive 4点セット永続化`, `live_criteria新閾値`, `v1/v2混在防止` の5系統を追加。

**全体判定**
- **CHANGES_REQUESTED**  
主因は S1/S2/S8/S9/S11 の重大な伝搬・互換・意味整合リスクです。特に「旧新キー移行の原子的反映」と「閾値意味の再定義」を先に固めるべきです。