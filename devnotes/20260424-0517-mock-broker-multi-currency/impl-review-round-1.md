## Verdict
NEEDS_REVISION

## 主要論点
- `MockBroker.__init__` の per-pair home 解決は設計意図どおりです。`home_currency=None` で `meta.quote_currency` を採用し、不一致時 `NotImplementedError` に `Phase 4` と `fx_rate_provider` を含みます（[mock.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/src/broker/mock.py#L103), [mock.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/src/broker/mock.py#L111)）。
- scale 不変性テストは反証可能な形です。S2 は `initial_cash×units` 同時10倍で Sharpe 差分閾値を検証し、`margin_call` 非発生も assert しています（[test_mock_multi_currency.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/tests/broker/test_mock_multi_currency.py#L361), [test_mock_multi_currency.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/tests/broker/test_mock_multi_currency.py#L375)）。S3 は returns 要素一致を検証しています（[test_mock_multi_currency.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/tests/broker/test_mock_multi_currency.py#L399)）。
- `InstrumentMeta(...)` の伝搬は scripts 7 + paper_trade + helper/test 側で `pip_size/display_precision` が明示または quote 由来ヘルパで設定され、JPY fixture の沈黙 default 混入リスクは実運用経路で解消されています（例: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/scripts/alpha_factory/run_ga.py#L231), [paper_trade.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/scripts/paper_trade.py#L64), [tests/_helpers.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/tests/_helpers.py#L13)）。
- `fx_rate_provider` 命名は `mock.py` / `margin.py` / docs で統一されています（[mock.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/src/broker/mock.py#L111), [margin.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/src/broker/margin.py#L16), [cross-pair.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/docs/alpha_factory/cross-pair.md#L151), [terminology.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/docs/alpha_factory/terminology.md#L316)）。
- `cross_pair.py` 本体は未変更ですが、`_run_pair_sharpe -> MockBroker(instrument_meta=meta)` が T019 後に非 JPY-quote でも有効になった点は整合しています（[cross_pair.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/src/alpha_factory/cross_pair.py#L142)）。
- ただし docs 整合に不一致があります。`cross-pair.md` は「T019で解消した範囲」を明示している一方、`terminology.md` の `ANCHOR_PAIRS` 定義は旧制約（構造的 pair_failure 発生）を残しています（[cross-pair.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/docs/alpha_factory/cross-pair.md#L141), [terminology.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/docs/alpha_factory/terminology.md#L255)）。

## 必須修正（NEEDS_REVISION 時のみ）
- `devnotes/20260424-0517-mock-broker-multi-currency/` に `conceptual-design.md` / `detailed-design.md` を配置してください（現状は `.codex-prompt-impl-review.md` と `.codex-session-impl-review.jsonl` のみで、C1 design-first 監査が完全実行不能）。
- `terminology.md` の `ANCHOR_PAIRS` 説明を T019 後の状態に更新し、`cross-pair.md` と矛盾しない表現に統一してください（[terminology.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/docs/alpha_factory/terminology.md#L255)）。

## 推奨修正（任意）
- S3 にも `margin_call` 非発生 assert を追加し、S2/S3 両方で非拘束条件を明示すると反証可能性がさらに強くなります（[test_mock_multi_currency.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/tests/broker/test_mock_multi_currency.py#L399)）。
- `cross_pair.py` 先頭コメントの「Phase 2 では構造的 pair_failure」記述は現状とズレるため更新推奨です（[cross_pair.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T019/src/alpha_factory/cross_pair.py#L58)）。

## 根拠
- Fact: `MockBroker` は `home_currency=None -> quote`、不一致時 `NotImplementedError` に `Phase 4`/`fx_rate_provider` を含む。Interpretation: 観点1は充足。
- Fact: S2 は Sharpe 不変 + `margin_call` 非発生を明示、S3 は returns 一致を要素比較。Interpretation: 観点2は概ね充足（S3の非拘束 assert は任意強化）。
- Fact: scripts/paper/helper/test の対象 `InstrumentMeta` で `pip_size/display_precision` 伝搬が確認可能。Interpretation: 観点3は実質充足。
- Fact: `fx_rate_provider` 文言はコード/主要docsで一致。ただし設計本体2ファイルが欠落。Interpretation: 観点4は実装面OKだが監査証跡不足。
- Fact: `cross_pair.md` と `terminology.md` が T019 の制約解消有無で矛盾。Interpretation: 観点6未充足のため `NEEDS_REVISION`。