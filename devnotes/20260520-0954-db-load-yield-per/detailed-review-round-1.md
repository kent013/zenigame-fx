**全体判定**: `CHANGES_REQUESTED`

**施策別判定**
1. `C-1` `_load_lane_bars` streaming化: `REQUEST_CHANGES`  
2. `C-2` `load_aux_pair_bars_index` streaming化: `REQUEST_CHANGES`  
3. `C-3` `bars_digest` 追加: `APPROVE`  
4. `C-4` phase marker RSS logger: `APPROVE`  
5. `C-5` smoke計測・判定: `INCONCLUSIVE`  

**Fact（観察事実）**
- C-1/C-2 は `select(PriceBarM1)` + `.all()` から、列タプル `select(*columns)` + `execution_options(yield_per=N)` + `for row in session.execute(stmt)` へ置換する設計。
- C-1 は `SessionLocal()` 内部生成、C-2 は caller-owned `db_session` を受ける。
- C-3 digest は `Decimal` を `str()` 直列化し、`complete` を含めて `sha256` で比較する設計。
- C-4 は `psutil` で RSS 計測し、例外時は `-1.0` を記録して継続する設計。
- C-5 は smoke で main RSSピーク差分を判定し、必要時のみ batch size 5,000 を追加比較する設計。

**Interpretation（解釈・評価）**
- 列タプル化自体は identity map 汚染回避として妥当。`PriceBarM1` entity を積まない点は設計意図に合致。
- ただし server-side cursor を使う設計では「途中例外時の Result クローズ」を明示しないと、特に caller-owned session 側でカーソル/トランザクション状態を引きずるリスクが残る。
- digest 設計は「旧経路と新経路の意味的同値性検証」という用途に十分実用的。
- smoke 判定は現状のプロセス抽出方法だとノイズ混入余地があり、結論の確度が不足。

---

**指摘事項（重要度順）**

1. [Warning] C-1/C-2: 途中例外時の `Result` 未クローズリスク  
修正案: `result = session.execute(stmt)` を `try/finally` で囲み `result.close()` を必ず実行。  
特に C-2 は caller-owned session なので、早期 `ValueError`（重複minute検知）での残存カーソルを避けるべきです。

2. [Warning] C-5: RSS計測のプロセス抽出が広すぎ、判定ノイズが出る可能性  
修正案: `run_ga` 親PID起点で子プロセスツリーを辿って集計する方式に変更（無関係Pythonプロセスを除外）。  
これをしないと `>=1GB` 判定が偽陽性/偽陰性になり得ます。

3. [Warning] C-1テストモック: `execute()` shim が `SimpleNamespace` のみだと SQLAlchemy `Row` 差異を取りこぼす可能性  
修正案: テストダブルを「属性アクセス + `row[0]` + `_mapping`」の最低互換を持つ形にするか、`_stream_bars` を属性アクセス専用契約として明文化し、その契約テストを追加。

4. [Suggestion] C-3 digest: `pair_name` も行に含めると誤比較耐性が上がる  
修正案: 同一バー値で通貨ペアだけ異なるケースを確実に区別したいなら `pair_name` を canonical field に追加。

5. [Suggestion] C-4: `psutil` 例外時に例外型だけ debug/warn で残す  
修正案: `main_rss_mb=-1.0` に加え `error_type` を出すと運用時の切り分けが速くなります。

---

**特に確認したい点への回答**

1. `_stream_bars` + 列タプル + `yield_per` で identity map 汚染回避  
- 妥当です。entity非選択なので `PriceBarM1` は identity map に載りません。  
- psycopg3 の server-side cursor は SQLAlchemy設計上有効化される前提で整合していますが、実証は統合テストで担保すべきです。

2. `_MockSession` と `execute()` 経路  
- そのままだと壊れる可能性があります。`execute` shim追加は必須。  
- `row.bar_time` 前提なら属性アクセス互換を担保すれば十分ですが、Row互換範囲を明確化してください。

3. caller-owned session の transaction state 共有リスク  
- あります。特に例外中断時。  
- `Result.close()` の明示と、関数内での完全消費/早期close契約でリスクを抑えられます。

4. `Decimal str()` で桁落ち検出できるか  
- 本用途（旧/新ロード経路比較）では妥当。`Numeric(12,6)` の trailing zero 差異検知も可能。  
- ただし将来 float変換を挟む経路には無力なので、テストで防衛するのが前提です。

5. batch size 10,000 妥当性  
- 初期値として妥当。極端に攻めた値ではありません。  
- 最終判断は smoke 実測依存で、現時点は `INCONCLUSIVE` が正しいです。

6. phase marker RSS logger の例外処理  
- 継続性の観点では十分。  
- 監視運用の可観測性を考えると、例外型ログを追加する方が堅いです。

---

**監査discipline適合メモ**
- `C1` Design-first: 準拠（設計文書ベースで評価）。  
- `C2` 不在=バグ禁止: 準拠。  
- `C3/C7` 相関・サンプル: 本件は主に実装設計で該当薄。  
- `C4` 前提検証: 一部は文書主張ベースのため実行時検証は未了。  
- `C8` INCONCLUSIVE: C-5に適用。  
- `C9` Falsification-first: 「例外時カーソル残存」「計測ノイズ」を先に反証対象として指摘済み。