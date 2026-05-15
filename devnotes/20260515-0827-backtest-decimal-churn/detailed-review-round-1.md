**前提検証 (C4)**
- Fact: ご指定どおりコマンド実行なしで、提示テキストのみを根拠にレビューしました。
- Interpretation: `最新 main との snippet 一致` と `consumer 全列挙の網羅` は実地照合できないため、C4/C2 は一部 `INCONCLUSIVE` になります。

**施策1 判定: REQUEST_CHANGES**
- [Critical] `EquityCurve` は raw の `np.ndarray` を公開する設計ですが、文言上の「read-only 契約」だけでは実際の破壊的書き換えを防げません。  
  修正案: [equity_curve.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/equity_curve.py) の `__post_init__` で `setflags(write=False)` を強制し、`dtype=int64`・`C-contiguous` も検証して不正入力は fail-closed。
- [Warning] `decode_epoch_ns` が `epoch_ns % 1000 != 0` を黙って切り捨てる仕様です。  
  修正案: 非 1000 倍数を `EquityCurveError` で reject し、lossless 契約を明示的に守る。
- [Warning] `SCALE=8` 前提は妥当ですが、将来 `holding_cost_per_day_bps>0` 有効化時に実行中 fail まで気づけません。  
  修正案: 起動時に「現在の config で SCALE 契約成立」を事前検証するガードを追加。

**施策2 判定: APPROVE**
- Fact: `run_backtest` の retain される小オブジェクトを `EquityCurveBuilder` に置換する方向は、問題設定（arena 断片化）と整合しています。
- Interpretation: Decimal を約定・証拠金計算に残しつつ保存表現だけ整数化する分離は、金額計算の load-bearing 領域を壊していません。

**施策3 判定: APPROVE**
- Fact: `max_drawdown` を整数演算、`max_drawdown_pct/calmar` を decode 後の既存 Decimal 経路で計算する分離方針は、bit-exact 主張として筋が通っています。
- Interpretation: tie-break（`dd > max_dd`）維持の明記は適切です。  
- [Warning] shadow test に「同一 `max_dd` が複数回出る系列」の固定ケースが明示されていません。  
  修正案: `equal-dd different-peak` ケースを1本追加して peak 選択の同値性を固定化。

**施策4 判定: INCONCLUSIVE**
- [Critical] 「consumer 全数確定」の主張は、最新 main 実体との照合証跡が設計書内にありません。禁止事項 8（4段接続漏れ）観点で未証明です。  
  修正案: [engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py) 変更コミット SHA を基準に、`equity_curve` 参照箇所の機械抽出結果（対象ファイル・関数）を devnotes に添付。
- [Warning] [ensemble.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/ensemble.py) の scaled-int 合算は、実装次第で `int64` オーバーフローが silent に起きます。  
  修正案: Python `int` で合算→範囲検証→`np.int64` 代入、または checked add を実装。

**施策5 判定: REQUEST_CHANGES**
- [Warning] 「archive diff」の比較規約が曖昧です。row-order 決定論 (L2) を見るなら比較手順の正規化が必要です。  
  修正案: 同一 seed で生成した archive を「同一ソートキー・同一 serializer」で byte-level 比較し、差分 0 を合格条件に明記。
- [Warning] serialized parity は良いですが、`NaN/None` を含むフィールド比較ルールが未定義です。  
  修正案: `NaN 同値規約` と `Decimal 文字列化規約` をテストヘルパで固定。

**全体判定: INCONCLUSIVE**
- Fact: 設計の中心仮説（retain object 削減で RSS 断片化源を断つ）は妥当です。
- Interpretation: ただし C4/C2（最新 main 一致と consumer 網羅）の検証証跡不足、および immutability/overflow の設計穴が残るため、現時点で `APPROVED` にはできません。

**先人の知恵（根拠）**
- Paul R. Wilson et al., 1995, *Dynamic Storage Allocation: A Survey and Critical Review*  
- Wes McKinney, 2010, *Data Structures for Statistical Computing in Python*  
- Charles R. Harris et al., 2020, *Array programming with NumPy*