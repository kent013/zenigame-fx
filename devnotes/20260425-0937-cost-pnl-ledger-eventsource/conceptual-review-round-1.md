**全体判定: CHANGES_REQUESTED**

**前提検証 (C1/C4/C9)**
Fact:
- `total_pnl` は現行 backtest で `sum(Trade.pnl)` として計算されています。[src/backtest/metrics.py#L85-L89](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L85)
- `Trade.pnl` には closing 時点で `raw_pnl - holding_cost` の `net_pnl` が入ります。[src/broker/mock.py#L327-L353](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L327)
- Stage A の payload は `trade_count` と `sharpe_raw` を持ちますが、`total_pnl` は持ちません。[src/alpha_factory/stage_gate.py#L268-L333](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L268)
- archive への Stage A collect も `trade_count` と `sharpe` だけを書き、`total_pnl` は書きません。[src/alpha_factory/archive.py#L322-L346](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L322)
- 設計文書も `total_pnl / trade_count` は Stage A では `- / ○`、Stage B/C で上書きと明示しています。[docs/alpha_factory/clause-architecture.md#L356-L365](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L356)
- 既存合意は「Run 10 では監査のみ、挙動非変更」です。[devnotes/20260425-0931-fx-improve/improvement-plan.md#L7-L10](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md#L7)
- 別分析メモでも、原因は「Stage A 失敗個体で `total_pnl` が archive 未転記の経路」と整理されています。[devnotes/20260425-0931-fx-improve/post-review-codex-signal-quality.md#L1-L4](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/post-review-codex-signal-quality.md#L1)

Interpretation:
- 現状のコードと文書を前提にすると、`trade_count>0 ∧ archive.total_pnl==0` はまず「PnL 集計破綻」ではなく「Stage A 行に total_pnl を載せていない記録仕様」で説明できます。
- したがって、この概念設計の中核仮説は未反証ではなく、むしろ現行 SSOT と衝突しています。

## 1. 使命との整合性
- [Warning] live_criteria の信頼性向上には寄与しますが、Run 9 の主 failure mode として既に合意されているのは「無取引優位」です。ledger 全面刷新は使命への直接距離が一段遠いです。修正提案: Phase 1 を「record consistency 監査 + Stage A 行への `total_pnl` 可視化」に縮小してください。

## 2. 禁止事項違反
- [Warning] `production GA モードで violation を fitness_pen で減点` は、実質的に fitness 経路へ新しい介入を入れる提案です。現段階では `GAハック` と誤解されやすく、少なくとも「既存 Stage A/B/C を touch しない」とも整合しません。修正提案: 初回はログ/diagnostics のみ、選抜や fitness には一切影響させないでください。

## 3. 実現可能性
- [Warning] 現行 `Trade` は `pnl` しか持たず、`spread/slippage/swap/fee` の分解欄がありません。[src/broker/orders.py#L32-L43](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py#L32) 現行 broker で明示的に扱っているコストは holding cost のみで、spread は bid/ask 約定価格に埋め込まれています。[src/broker/mock.py#L327-L348](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L327) 修正提案: 先に「何を明示コストとして分解可能か」の taxonomy を確定し、`spread` は暗黙コストのまま扱うのか、別列で再構成するのかを設計で固定してください。

## 4. 期待効果の妥当性
- [Critical] `trade_count>0 ∧ total_pnl==0` を「構造的矛盾」と断定している点が成立していません。archive 側の Stage 投影仕様だけで説明可能です。修正提案: 仮説を「PnL 集計バグ」から「Stage A 記録不整合 or 表示不整合」へ引き下げ、先に falsification 用の tracing を置いてください。
- [Critical] invariant I1 `trade_count > 0 ⇒ total_pnl != 0.0` は不正です。損益が相殺されて厳密に 0 になる取引列はあり得ます。修正提案: I1 は `trade_count > 0 ⇒ total_pnl が SSOT から導出済みである`、または `archive 上の metric_stage と整合する` に置き換えてください。

## 5. リスク
- [Warning] 誤った invariant を production penalty に接続すると、正常個体を異常扱いして淘汰します。修正提案: invariant はまず CI 限定、production では fail-open の監査ログだけにしてください。
- [Warning] archive schema 追記は `calibrate_gate`、run report、tests まで波及します。[src/alpha_factory/archive.py#L54-L84](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L54) 修正提案: schema 変更前に downstream consumer 一覧を明示し、互換性テストを受け入れ条件に入れてください。

## 6. スコープの適切さ
- [Warning] 既存合意は audit-only なのに、本案は backtest SSOT、broker、archive、診断、production penalty まで含む大きい refactor です。修正提案: `A. 原因切り分け`, `B. 記録修正`, `C. cost ledger 拡張` の 3 TODO に分割してください。

## 7. メモリ制約
- [Suggestion] worker-local で数千 fill 規模なら 3GB 制約には概ね収まる見込みです。ただし archive 前に全 fill を長寿命保持する必要は薄いです。修正提案: ledger を永続保持ではなく `reduce 用の軽量 accumulator + optional sampled trace` に寄せる方が安全です。

## 8. 前提検証 (C4)
- [Critical] 前提「PnL 集計経路の破綻」は最新コードと一致していません。現行実装では backtest 側で `total_pnl` は既に直接計算され、archive Stage A で未転記なだけです。修正提案: 前提欄を `verified / unverified` に分け、`verified: Stage A archive rows omit total_pnl`、`unverified: backtest PnL aggregation bug` と書き換えてください。

## 9. Design-first 原則 (C1)
- [Critical] 現行文書は既に Stage 別カラム射影を定義済みなのに、その設計差分を読んだ痕跡が概念設計に反映されていません。[docs/alpha_factory/clause-architecture.md#L356-L365](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L356) 修正提案: この案を続けるなら、冒頭に「既存仕様との差分」として `Stage A total_pnl omission` を明示し、その上で「なぜ omission 修正では足りず ledger SSOT が要るのか」を追加してください。

**結論**
Fact:
- 現時点で確認できる範囲では、観測された `trade_count>0 ∧ total_pnl=0` は ledger 不在よりも archive 投影仕様で説明しやすいです。
- 既存合意ともズレています。

Interpretation:
- この概念設計は現状のままでは通せません。
- 通すなら「PnL 単一台帳」ではなく、まず「Stage A 記録整合性監査」に縮小した再提出が必要です。