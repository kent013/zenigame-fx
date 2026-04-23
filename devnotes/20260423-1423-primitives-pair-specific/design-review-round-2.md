**レビュー結果（Must-fix 5件）**
Blocking な未解消項目は見当たりません。Round 1 の 5件は設計上いずれも解消されています。

1. `atr` 抜け: `_BARS_PROVIDED_KEYS` で補完済み  
Fact: [detailed-design.md:161](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:161) に `atr` 含有。  
Interpretation: preflight 網羅性の欠落は解消。

2. 既存テスト `==20` 破綻: 更新方針を明示  
Fact: [detailed-design.md:23](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:23) 以降で3ファイルの更新方針を具体化。  
Interpretation: 後方互換テスト破綻への対処は設計に反映済み。

3. P8 の `required_data` 不整合: OR 依存を型で表現  
Fact: `optional_data_groups` 追加（[detailed-design.md:91](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:91), [detailed-design.md:224](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:224), [detailed-design.md:859](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:859)）。  
Interpretation: fail-fast 漏れの主因は解消。

4. `strict_snapshot_required` / `strict_aux_required` の責務混線: 明文化済み  
Fact: 責務表を追加（[detailed-design.md:271](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:271)）。  
Interpretation:運用時の解釈ブレは大幅に減少。

5. 未使用 import: 除去方針を反映  
Fact: import を最小化（[detailed-design.md:322](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:322)）。  
Interpretation: Round 1 指摘の論点は解消。

**非ブロッカー（任意修正）**
1. `selected_key` が未使用変数です。  
Fact: [detailed-design.md:828](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:828), [detailed-design.md:831](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:831)。  
Interpretation: `ruff` 設定次第で警告対象になり得ます。

2. `_aligned_pair_close` の doc と実装が一部不一致です。  
Fact: doc は「`aux_bars is None` で ValueError」と読める一方、実装は NaN 配列返却（[detailed-design.md:371](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:371), [detailed-design.md:375](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:375)）。  
Interpretation: 仕様誤読防止のため文言合わせを推奨。

**判定: APPROVED**