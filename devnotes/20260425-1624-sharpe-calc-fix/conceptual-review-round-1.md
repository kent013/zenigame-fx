**本分析の前提**
- Verified: 提示文の抜粋上、現行 `sharpe` は「M1 全 bar の equity 変化率」を母集団にし、`√BARS_PER_YEAR_M1` で年率化している。
- Verified: 提示文の抜粋上、提案は「trade-level Sharpe へ置換」「`trade_count_min_for_sharpe` 未満は `None`」「archive に `sharpe_calc_version` 追加」を含む。
- Unverified: reader/report/query 側が `sharpe_calc_version` を必ず解釈するかは、提示文だけでは確認できない。
- Unverified: DSR が現行で gate 判定に使われているか、単なる補助統計かは、提示文だけでは確認できない。
- Unverified: 1 戦略内で同時複数ポジションを許すか、`equity_at_open` を denominator にしてよい実装前提かは、提示文だけでは確認できない。

**全体判定**
CHANGES_REQUESTED

**総評**
bar-level annualized Sharpe の artifact を是正したい、という問題設定自体は使命整合です。  
ただし、この概念設計のままでは「Sharpe の意味論」「live_criteria の再定義」「archive/reader 後方互換」の3点が未固定で、新しい指標バグや比較不能状態を作るリスクが高いです。

1. [Critical] 使命との整合性  
Facts: 提案は現行の bar-level annualized Sharpe を捨て、raw trade Sharpe を Phase 1 の主指標にする。`trade return` の定義は `pnl / equity_at_open` と `pnl / risk_unit` の二案のまま未確定。  
Interpretation: 使命は live_criteria を満たす個体の発見です。分母が未確定のままでは、Sharpe の値自体が pair 間・run 間で比較不能です。ここが曖昧なままでは「artifact 修正」ではなく「評価軸の再発明」になります。  
修正提案: Phase 1 着手前に return 単位を 1 つに固定してください。私の推奨は「口座基準通貨に換算した net pnl（spread/swap/slippage 控除後） / entry 直前口座 equity」です。`risk_unit` を採るなら、その定義・算出経路・cross-pair 比較可能性まで同時に固定が必要です。

2. [Critical] 禁止事項違反の疑い  
Facts: 提案は Phase 1 の DoD に `live_criteria.sharpe_min` の暫定再校正（例 0.3）を含めている。  
Interpretation: これは「意味論変更に伴う必要な再校正」という面はありますが、実証なしの閾値緩和に見えます。禁止事項 4 に極めて近いです。  
修正提案: Phase 1 では `live_criteria` を直接上書きしないでください。`candidate_trade_sharpe_min` のような暫定 gate を別名で導入し、旧 `live_criteria.sharpe_min` との対応表は archive replay 後に決めるべきです。閾値変更は top-N archive 再計算と cross-pair 再評価を根拠にした別 TODO に分離するのが妥当です。

3. [Warning] 実現可能性  
Facts: 影響範囲として GA fitness, Stage A, cross-pair, Alpha Sieve, calibrate_gate, DSR, archive が列挙されている。  
Interpretation: 実装量自体は大きすぎませんが、「新 Sharpe を全経路に統一する」なら値伝搬漏れの温床です。特に zenigame 系で多発した `config → GaConfig → meta → consumer` と `schema → row_template → collect → flush` の4段漏れが再発しやすい構図です。  
修正提案: 概念設計に propagation checklist を明記してください。少なくとも `config 定義 / metrics API / genome.meta / archive schema / reader / report / logger` の 7 点を DoD に昇格させるべきです。

4. [Critical] 期待効果の妥当性  
Facts: 提案は H1/H2/H3 を置いているが、現時点では再計算結果はまだ示されていない。`trade_count_min_for_sharpe=30` は推奨値として置かれている。  
Interpretation: 「Sharpe 18 は artifact の可能性が高い」は妥当です。ただし「Run 9-10 の探索結果はすべてハック個体」という断定は、提示事実だけでは過剰です。C8/C9 的には、まず replay で反証を探すべきです。また N=30 は経験則であって、理論的に強い根拠ではありません。Andrew W. Lo, 2002, *The Statistics of Sharpe Ratios* は Sharpe 推定の不安定性と独立性仮定の弱さを強調しています。Bailey and López de Prado, *The Deflated Sharpe Ratio*（年・題名は要確認）も sample size と selection bias を重く見ています。  
修正提案: 断定文を弱めてください。`trade_count_min_for_sharpe` は config 化し、N=20/30/50 の感度分析を replay で先に実施する、という仮説検証計画に変えるべきです。

5. [Critical] リスク  
Facts: 後方互換案は `sharpe_calc_version` 列追加が中心で、既存 `sharpe` 列は再利用する構成に読める。cross-pair 側で `None` をどう集計するかは未記述。  
Interpretation: version 列だけでは不十分です。reader/report/query が version を見落とした瞬間に、旧値と新値が同じ `sharpe` として混ざります。また `trade_count < N_MIN` を `None` にした場合、cross-pair 集計が skip 扱いだと「難しいペアで無取引」が抜け道になります。  
修正提案: reader 側は `unsupported sharpe_calc_version` を hard-fail にしてください。さらに cross-pair は `None` を fail-fast 扱いに固定すべきです。可能なら `sharpe` 列を上書きせず、`trade_sharpe_raw` のような別名列にして意味論を露出した方が安全です。

6. [Warning] スコープの適切さ  
Facts: Phase 1 に metric 置換、全 consumer 切替、archive 変更、暫定 live_criteria 再校正まで入っている。DSR の意味論変更は Phase 2 に送っている。  
Interpretation: 「metric plumbing だけを先に通す」なら適切です。しかし「閾値再校正」まで同梱すると Phase 1 が設計変更と運用判定変更を同時に抱え、レビュー軸が濁ります。  
修正提案: Phase 1 を 2 つに割るのがよいです。Phase 1A は `trade_sharpe_raw` 実装と reader hard-fail まで。Phase 1B は replay に基づく gate 校正。これなら禁止事項への抵触も減ります。

7. [Suggestion] メモリ制約  
Facts: trade-level 集計は bar-level より対象点数が少ない。実行環境は 24GB × 6 worker。  
Interpretation: この変更はメモリ面ではむしろ有利です。重大な悪化は見えません。  
修正提案: 実装時は trade close 時点で平均・分散を逐次更新し、全 trade return 配列を巨大に保持しない設計にしてください。6 worker 並列でも安全側に寄せられます。

8. [Critical] 前提検証  
Facts: DSR は「bar 単位 non-annualized Sharpe 前提」と設計文に明記されている一方、Phase 1 では本格対応を後ろ倒しにしている。annualize しない raw trade Sharpe を採る案もある。  
Interpretation: `annualize しない raw trade Sharpe` は内部順位付け指標としては合理的ですが、業界標準の「Sharpe」と同名で扱うと誤読を誘発します。名前が役割を示す、という原則にも反します。DSR も同じ名前空間に置くなら、Phase 1 時点で「無効」か「旧定義専用」を明示しないと意味論が壊れます。  
修正提案: Phase 1 では名称を `trade_sharpe_raw` に固定し、`sharpe` という総称は使わない方が安全です。DSR は `trade_sharpe_raw` では未対応として明示的に停止または非表示にしてください。

**採否の要点**
- 承認できる核: 「bar-level annualized Sharpe artifact を潰す」という問題設定。
- 修正必須: return 単位の固定、`live_criteria` 緩和の分離、reader 側後方互換、cross-pair の `None` fail-fast、名称の明確化。
- この5点が固まれば、概念設計としてはかなり通しやすくなります。