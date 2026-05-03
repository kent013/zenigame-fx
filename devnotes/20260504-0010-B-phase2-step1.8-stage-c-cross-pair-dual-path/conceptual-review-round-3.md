**全体判定**
`APPROVED`

案 `A'` は採用でよいです。Round 2 の 3 Critical、すなわち sidecar 永続化、`MappingProxyType` pickle 失敗、循環依存は概念設計上は解消されています。`CrossPairResult` を sanitize してから `cross_pair_payload["result"]` に残す方針は、`parallel_eval._extract_cross_pair_result` 経由の `GenomeStageResult.cross_pair` まで見ても整合します。

**本分析の前提**
- Facts: `CrossPairResult` は現状 `src/alpha_factory/stage_gate.py:544` にあり、`cross_pair.py` が `stage_gate.py` から import しています。
- Facts: `cross_pair_payload["result"]` は `src/alpha_factory/stage_gate.py:1555` に格納され、`src/alpha_factory/parallel_eval.py:372` で抽出されます。
- Facts: `dict` + `field(default_factory=dict, repr=False, compare=False)` の最小 pickle 検証は成功しました。
- Interpretation: Round 3 の sanitize 設計は、payload / IPC / archive への sidecar 漏れを止める構造になっています。

**Critical**
- なし。

**Warning**
- [Warning] §2.2 に `default は MappingProxyType({})` という Round 2 の残骸があります。  
Facts: §2.3 では `field(default_factory=dict, repr=False, compare=False)` に修正されています。  
Interpretation: 実装者が §2.2 を拾うと Round 2 の pickle 問題が再発します。  
修正提案: §2.2 の該当文を `default は dict の default_factory` に修正してください。

- [Warning] A1 の「cross_pair_payload 全件が 1 byte も変化しない」は、E2 と厳密には矛盾します。  
Facts: E2 は payload 内 `CrossPairResult._shadow_sidecar_inputs == {}` を許容・検証します。  
Interpretation: dataclass field が増える以上、`__dict__` や `asdict` ベースの byte snapshot では完全一致しません。  
修正提案: A1 は「既存 public keys / existing metrics / passed / reason_codes が不変、`_shadow_sidecar_inputs` は空 dict で除外比較」に変更してください。

- [Warning] §1.4 の「cross_pair_payload / cp_result の既存属性は絶対 touch しない」は sanitize と表現上衝突します。  
Facts: §2.4 は `cross_pair_payload["result"] = replace(...)` を行います。  
Interpretation: 意図は「既存判定値・metrics に触らない」なので、payload result 差し替え自体は禁止ではありません。  
修正提案: 「既存判定値・metrics・reason_codes は touch しない。sidecar sanitize のため result 参照だけ差し替える」に修正してください。

**Suggestion**
- [Suggestion] E4 の non-empty pickle test は残してよいですが、主目的は sanitize 後 payload の pickle 互換です。  
Facts: 実運用で親プロセスへ渡るべきなのは sanitized result です。  
Interpretation: non-empty sidecar pickle は防御的テストとして有用ですが、必須安全性は E2/E6 です。  
修正提案: E4 は「non-empty も成功すれば望ましい」、merge 必須は「sanitize 後 `GenomeStageResult` が pickle 可能」に寄せると実運用契約により一致します。

**方向性判断**
- 採用案: `A'`
- 理由: ii-lite constituent observability を満たしつつ、canonical 計算責務を `stage_gate.py` に閉じ、`CrossPairConfig` / `parallel_eval.py` / `swim_lane.py` の伝搬面を増やしていません。
- 結論: 上記 Warning の文言修正を詳細設計前に反映すれば、概念設計として進行可能です。