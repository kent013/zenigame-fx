**前提（C4 / C9）**
1. 反証優先で、概念設計・Round2指摘・詳細設計・現行実装の整合破綻点を先に確認しました。  
2. 事実と解釈は分離して記載します（C6）。統計サンプル論点（C7）は本レビュー対象外です。

**主要所見（Severity順）**
1. **preflight verify が `RequiredDataKey` を全網羅していません（`atr` 抜け）**  
Fact: `RequiredDataKey` には `atr` が存在しますが、preflight の「barsで提供済み」判定に `atr` が入っていません（[detailed-design.md:123](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:123), [detailed-design.md:157](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:157), [_base.py:38](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_base.py:38)）。  
Interpretation: `strict_aux_required=True` 時に将来 `required_data=("atr", ...)` を使う primitive が誤って `unknown required_data key` 扱いになり、完全性要件に未達です。  

2. **既存テスト不変の前提が崩れる設計なのに、既存テスト更新計画が欠けています**  
Fact: `ensure_registered()` に pair-specific を追加する設計です（[detailed-design.md:979](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:979)）。一方、現行テストは `total=20` / `pair_specific=0` を固定期待しています（[test_modulator_generic.py:200](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_modulator_generic.py:200), [test_modulator_generic.py:225](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_modulator_generic.py:225), [test_directional_generic.py:159](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_directional_generic.py:159), [test_primitives_registry.py:241](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_primitives_registry.py:241)）。  
Interpretation: 「F1-F14/M1-M6テスト不変」のDoDを満たせない可能性が高く、後方互換の記述が不十分です。  

3. **P8 の `required_data` と実行経路が不整合です（fail-fast 漏れ）**  
Fact: `use_copper=0` では `macro.commodity_index` を参照しますが、`required_data` は `macro.copper` 固定です（[detailed-design.md:703](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:703), [detailed-design.md:730](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:730), [detailed-design.md:736](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:736)）。  
Interpretation: `strict_aux_required` が有効でも `commodity_index` 欠損を preflight で検知できず、値伝搬漏れを許す設計です。  

4. **`strict_snapshot_required` と `strict_aux_required` の責務境界が混線しています**  
Fact: snapshot 以外の aux 欠損（P5/P8/P9/P12）でも `strict_snapshot_required` で RuntimeError を出す設計です（[detailed-design.md:535](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:535), [detailed-design.md:706](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:706), [detailed-design.md:752](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:752), [detailed-design.md:924](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:924)）。  
Interpretation: API利用側の設定意図が曖昧になり、`strict_aux_required` の存在意義を弱めています。  

5. **lint通過リスク（未使用import）が残っています**  
Fact: `pair_specific.py` の案に未使用import候補があります（[detailed-design.md:210](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:210), [detailed-design.md:211](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:211), [detailed-design.md:212](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:212)）。  
Interpretation: DoD の `ruff` 通過条件（[detailed-design.md:1077](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:1077)）に抵触する可能性があります。  

**解消確認できた点**
1. Round2 の3指摘（型、3状態、preflight入力境界）は詳細設計上は明文化済みです（[detailed-design.md:62](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:62), [detailed-design.md:1036](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:1036), [detailed-design.md:1045](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:1045)）。  
2. P10 の M4 差別化（USD/CAD固定 + NAセッション制限）は実装案に反映されています（[detailed-design.md:804](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:804), [detailed-design.md:815](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:815)）。  
3. P5 の misalignment fail-fast 契約は具体化されています（[detailed-design.md:269](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:269), [detailed-design.md:1042](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md:1042)）。

**判定**
**NEEDS_REVISION**