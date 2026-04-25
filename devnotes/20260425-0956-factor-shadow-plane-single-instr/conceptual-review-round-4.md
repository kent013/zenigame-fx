## 前提（本レビューの前提条件）
- `Verified`（文書内で確認可能）: dispatch matrix は 6 行で、`skipped_conditioning_mismatch` が追加されている。
- `Verified`（文書内で確認可能）: H1 の分母は `eligible_rows = bars >= window_days AND factor_data_available` に明記されている。
- `Verified`（文書内で確認可能）: H3 に「5 RUN セット連続 INCONCLUSIVE 時の再定義」ルールが追加されている。
- `Assumed`: Run 10 の H1 評価は `single instrument` かつ `factor_shadow.enabled=true` で実施する前提。
- `INCONCLUSIVE`: 実装コード未確認のため、DoD の「実装済み」判定自体は未確定（本レビューは概念設計文書のみ対象）。

## Critical（対応必須）
- 実行経路の矛盾（post-RUN 独立計算 vs collect_stage 書き込み）
  - Fact: 本文は「archive確定後に post-RUN 独立 task で実行」「GA worker 内では FSP 計算しない」と定義。
  - Fact: DoD D4c は「`collect_stage_*` で FSP 計算値を書き込む」と定義。
  - Interpretation: 同時には成立しにくく、値伝搬漏れまたは責務逸脱（GA worker 混入）を再発させる失敗経路になる。
- `assert` と graceful degradation の矛盾
  - Fact: 5b/D5 は件数不一致を `assert` と記述。
  - Fact: 同箇所で不一致時は `skipped_conditioning_mismatch` に倒して後段影響なし、と記述。
  - Interpretation: `assert` を厳密適用するとフォールバック前に停止しうるため、診断継続性の設計意図と矛盾する。

## Warning（対応推奨）
- enum 数の記述不整合
  - Fact: `fsp_runtime_mode` は実質 6 値（`active` + `skipped_*` 5 種）に見える。
  - Fact: D6/D7 は「active + skipped 6種」と記述。
  - Interpretation: テスト観点・ログ観点で「期待ケース数」の齟齬を生む。
- H1 の評価前提が本文で暗黙
  - Fact: H1 分母は改善済みだが、`single instrument` / `enabled=true` の前提が success criteria 本文に明示されていない。
  - Interpretation: 運用時に不適切な RUN を混ぜて誤判定する余地が残る。

## Suggestion（任意改善）
- FSP ライフサイクルを 1 行で固定: 「`collect_stage_*` は FSP 列を `null` 初期化のみ、値埋めは post-RUN updater のみ」。
- `assert` を「検知＋全行 `skipped_conditioning_mismatch` 付与＋警告ログ」に置換する設計文言へ統一。
- `fsp_runtime_mode` を「許容値一覧（6値）」として 1 箇所に定義し、D6/D7 と dispatch matrix の参照先を共通化。

## Round 3 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| Critical: D4 粒度不足 | 部分解消 | D4a〜D4d 分解は達成。ただし D4c と post-RUN 独立方針の整合が未確定。 |
| Warning: H1 分母定義 | 解消 | `eligible_rows` 定義が明示され、窓不足混入問題は改善。 |
| Warning: H3 長期 INCONCLUSIVE ルール | 解消 | 5 RUN セット連続時の再定義ルールが追加済み。 |
| Warning: `skipped_conditioning_mismatch` | 解消 | enum と dispatch 6 行目に反映済み。 |

## 総評と判定
**NEEDS_REVISION**

理由: Round 3 の指摘自体は概ね解消されていますが、設計としては **Critical 2件**（実行経路矛盾、`assert` とフォールバック矛盾）が残っています。ここを解消しないと、実装時に再び「値伝搬漏れ/記録漏れ」系の不具合を誘発する可能性が高いです。