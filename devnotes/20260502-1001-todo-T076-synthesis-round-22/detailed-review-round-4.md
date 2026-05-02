**全体判定**
- `APPROVED`
- Round 3 のブロッカーだった `SmokeObservabilityProjection` 実 field 不整合は解消しています。
- 残る懸念は PR 実装時の軽微調整で十分です。Round 5 は不要です。

**反証・弱点**
- [Suggestion] §13.3 の field 検証 loop は smoke.py 側の field 存在は確認しますが、§18.3 の DoD 表がその field 名を実際に参照しているかまでは検証しません。実装時に `SEC_18_3` 側にも同じ field loop を追加するとより堅いです。
- [Suggestion] §13.3 の grep は `SmokeObservabilityProjection` class 範囲に限定されていないため、同名 field が別 class にある場合に false positive になります。実装時は `awk '/class SmokeObservabilityProjection/,/^$/'` などで class 範囲を切るとよいです。
- [Suggestion] §22.2 のリンク `../../20260502-1001-todo-T076-synthesis-round-22/detailed-design.md` は、synthesis.md から sibling devnotes を指すなら `../20260502-1001-todo-T076-synthesis-round-22/detailed-design.md` が正です。PR 実装時に修正してください。
- [Suggestion] 「残り 18 top-level 章」は論理整理されていますが、§12 / §18 は top-level として未付与かつ subsection 部分付与済みなので、実装時に「§12/§18 を除く残り 18 top-level 章」と書くとさらに誤読が減ります。

**Fact**
- §6.3 の DoD 表は、主 SSOT を `SmokeDoDItem.status` に統一し、projection field を補助情報へ降格しています。
- §6.3 の関連 projection field は §C-7 実 field の `ab_divergence_class` / `epoch_consistency_class` / `warmstart_shortfall_class` / `bypass_ratio_class` / `session_entropy_class` / `dataset_epoch_id_present` と、cross-run の `cross_run_epoch_pollution_class` を使用しています。
- §9.3 / §9.4 の重複は解消されています。
- §22.2 は §9.3 と同じ top-level / subsection 分離を採用しています。
- Round 3 の optional suggestion だった dual-path 対応関係の同一行 grep は未対応です。

**Interpretation**
- DoD 表は「実 field との直結 SSOT」ではなく「DoD の主判定は `SmokeDoDItem.status`、projection は caller が参照する元値」という構造に整理され、T075 module との不整合は解消しています。
- §13.3 は完全な将来 drift 検出としてはまだ弱いですが、今回の docs-only PR を止めるほどではありません。
- dual-path の同一行 grep は品質向上案であり、Round 4 時点の承認ブロッカーではありません。

**Round 3 指摘別**
- [Critical] 1 DoD 表と SmokeObservabilityProjection 実 field 不整合: `解消`。主 SSOT / 関連 projection field の分離で矛盾は解消。
- [Warning] §13.3 field mismatch 機械検証不足: `部分解消`。smoke.py field 存在は検証可能。synthesis 表側の field 参照検証は実装時追加推奨。
- [Warning] §9.3 重複: `解消`。anchor 命名規則が §9.4 に移動済み。
- [Warning] 残り 18 章算定曖昧: `解消`。`anchorable clause unit` と top-level / subsection 分離で論理は通っています。
- [Warning] §22.2 提示不足: `解消`。本文提示により §9.3 との同期確認可能。ただし相対リンクは実装時修正推奨。
- [Suggestion] dual-path 対応関係の厳密 grep: `未解消`。optional として未対応で問題なし。必要なら PR 実装時に追加。

**実装時の調整**
- `SEC_18_3` に対して projection field 名の存在確認 loop を追加。
- smoke.py field grep を class 範囲に限定。
- §22.2 の detailed-design.md 相対リンクを `../20260502-1001-todo-T076-synthesis-round-22/detailed-design.md` に修正。
- 必要なら dual-path 3+1 の対応関係を exact line grep で補強。