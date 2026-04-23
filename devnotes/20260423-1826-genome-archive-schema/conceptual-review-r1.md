## 本分析の前提
- 概念設計本文と関連 SSOT を確認しました: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py), [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md), [statistics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py)
- `StageResult.metrics["payload"]` の実キーは Stage A/B/C それぞれ実装済み内容で確認しました。[stage_gate.py#L325](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L325) [stage_gate.py#L454](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L454) [stage_gate.py#L639](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L639)

## Verdict: NEEDS_REVISION

## Facts
- Parquet 永続化、flat scalar 列中心、`genome_json` にだけネストを寄せる方針自体は分析親和性が高く、目的とスコープも妥当です。[conceptual-design.md#L48](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L48)
- `bool nullable` の `ii_lite_pass` を Arrow/Parquet で扱う設計自体は問題ありません。[conceptual-design.md#L139](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L139)
- `fold_sign_ratio` / `sortino` / `calmar` / bootstrap CI を別 TODO に切る判断も、概念設計の段階では妥当です。[conceptual-design.md#L238](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L238)

## Interpretations
- 全体の方向性はよく、詳細設計に進める土台はあります。
- ただし監査性の核になる「4段伝搬契約」と「列意味論」に、いまのままだと実装時にブレる箇所が残っています。ここを閉じないまま進むと、後から archive の解釈が割れます。

## 修正点
1. `ii_lite_pass` の情報源を 1 つに固定してください。設計本文は「`StageResult.metrics["payload"]` から射影」と書きつつ、Stage C だけ `collect_stage_c(..., ii_lite_pass=...)` の別引数案を混ぜています。[conceptual-design.md#L64](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L64) [conceptual-design.md#L117](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L117) 既存 `StageResult` には `payload.cross_pair.result` がすでに入るので、archive 側はそこから導出する方が監査可能です。[stage_gate.py#L613](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L613)

2. 重複 collect の「後勝ち + WARN」は、ステージ順序を考慮しないと危険です。いまの記述だと、遅れて来た Stage A が Stage B/C の richer な値を潰しても仕様上は許容になります。[conceptual-design.md#L125](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L125) 少なくとも「同一 stage の再 collect」と「後段 stage による enrich」と「前段 stage の逆流」を分けて、前段→後段のみ上書き許可、逆流は WARN ではなく reject/ignore にすべきです。

3. `active_clause` の意味を揃えてください。 schema doc では「実際に発火した clause 数」ですが、概念設計では `weight != 0` の clause 数を入れる案になっています。[genome-archive-schema.md#L31](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L31) [conceptual-design.md#L88](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L88) これは別の指標です。列名を維持するなら runtime 発火数を取る設計に寄せる、今は structural proxy しか取れないなら schema/doc 側の定義を proxy に改めるべきです。

4. 行キーの定義を統一してください。「1 行 = `individual_name × generation`」と書きつつ、内部保持は `self._rows[individual_name]`、さらに仮説では「`individual_name` は 1 Run 内でユニーク」となっています。[conceptual-design.md#L48](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L48) [conceptual-design.md#L67](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L67) [conceptual-design.md#L125](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L125) 主キーが本当に `individual_name` だけなら generation は従属属性、そうでないなら duplicate 判定も in-memory key も複合キーに直す必要があります。

上の 4 点を閉じれば、他の観点は概ね問題ありません。特に flat schema、partial fill、nullable bool、open issue の切り分け方針は維持してよいです。