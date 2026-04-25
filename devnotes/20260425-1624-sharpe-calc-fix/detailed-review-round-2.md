1. **[Critical] `None` 補完ロジックが成立していません。**  
[`version = row.get("sharpe_calc_version", "v1_bar_annualized")`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-1624-sharpe-calc-fix/tmp/.codex-prompt-detailed-review-round-2.md:75) は「キー欠落時」しかデフォルト化せず、`{"sharpe_calc_version": None}` を補完できません。  
`nullable=True` 互換の主旨（旧データ `None` を v1 扱い）と矛盾するため、`row.get(...) or "v1_bar_annualized"` に修正が必要です。

2. **[Critical] `_trade_sharpe_raw` にゼロ除算リスクがあります。**  
[`len(returns) < trade_count_min` 判定](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-1624-sharpe-calc-fix/tmp/.codex-prompt-detailed-review-round-2.md:42) の後で、[`(len(returns)-1)` で分散計算](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-1624-sharpe-calc-fix/tmp/.codex-prompt-detailed-review-round-2.md:45) しています。`trade_count_min=1` 設定時に `len=1` で落ちます。  
`len(returns) < max(2, trade_count_min)` か、設定値の `>=2` バリデーションを固定してください。

3. **[Warning] `invalid_count` を caller が扱えません。**  
[`invalid_count` を増やして](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-1624-sharpe-calc-fix/tmp/.codex-prompt-detailed-review-round-2.md:32)、[`return rets  # caller が invalid_count を handle`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-1624-sharpe-calc-fix/tmp/.codex-prompt-detailed-review-round-2.md:39) となっており、設計意図とシグネチャが不整合です。  
`tuple[list[float], int]` 返却にするか、関数内で集約ログを完結させるかを決めてください。

4. **[Warning] v1/v2 フィルタは「未知バージョンの静かな混入」を検知できません。**  
[`== "v2_trade_level"` フィルタ](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-1624-sharpe-calc-fix/tmp/.codex-prompt-detailed-review-round-2.md:63) だけだと、将来値や破損値が無言で除外され、サンプル数低下だけが発生します。  
unknown version 件数を warning で可視化するか、一定割合超過で `INCONCLUSIVE/skip` に落とす設計を追加した方が安全です。

判定: **REQUEST_CHANGES**（上記 1,2 は実装前に潰した方がよいです）。