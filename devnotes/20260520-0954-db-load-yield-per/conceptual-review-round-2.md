**全体判定: APPROVED**

概念設計としては承認でよいです。Round 1 の Critical は本質的に解消されています。残る論点は詳細設計で潰すべき実装上の落とし穴で、現時点で概念設計を差し戻すほどではありません。

**Fact**
- `_load_lane_bars` は Stage B+A と holdout の両方で `.all()` を使っています。 [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:531)
- `load_aux_pair_bars_index` も `.all()` 後に `PriceBar` dict を構築しています。 [aux_loader.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py:584)
- `PriceBar` には `complete` が含まれます。現行の等価性チェック案は `complete` を checksum 対象に含めていません。 [price.py](/Users/ishitoya/repository/zenigame-fx/src/domain/price.py:16)
- `SessionLocal` は通常の SQLAlchemy `Session` で、streaming / server-side cursor の特別設定は現状ありません。 [connection.py](/Users/ishitoya/repository/zenigame-fx/src/db/connection.py:13)

**Interpretation**
- 施策 C は「DBロード時の二重保持仮説」を反証する最小手として妥当です。
- 24GB 制約の解決策ではなく、A/E へ進む前の低リスクな切り分け施策という位置づけも妥当です。
- ただし、`yield_per` 実装は ORM entity + `expunge_all()` では事故りやすいので、詳細設計ではより保守的な実装契約に寄せるべきです。

**残存指摘**

- [Warning] `expunge_all()` を caller-owned `Session` で使う設計は危険です。  
  `load_aux_pair_bars_index` は外部から渡された `db_session` を使う関数なので、内部で `session.expunge_all()` すると呼び出し側が保持している ORM entity まで detach する副作用があります。修正提案: 詳細設計では `select(PriceBarM1)` の ORM entity streaming ではなく、必要列だけの `select(...)` / `mappings()` / tuple row から `PriceBar` を構築し、identity map に載せない方針を第一候補にしてください。

- [Warning] 等価性 checksum に `complete` が抜けています。  
  `PriceBar` の意味論は `(pair_name, bar_time, bid, ask, volume, complete)` なので、checksum は `complete` も含めるべきです。`pair_name` は lane/pair ごとに分けて検証するなら省略可能ですが、stable digest の入力には入れてもよいです。

- [Warning] `hash checksum` は Python の組み込み `hash()` ではなく安定 digest に固定してください。  
  修正提案: canonical serialization した文字列または bytes に対して `sha256` を使う、と明記してください。Decimal は `str()` か正規化方針を固定し、datetime は UTC ISO か epoch integer に固定するのが安全です。

- [Warning] 0.5GB の Stop/Go 境界は n=1 + 5秒 sampling ではやや細かすぎます。  
  修正提案: `≥1.0GB` は n=1 でも Step C 合格判定可、`0.5〜1.0GB` は原則 n≥3 の median delta で部分成功判定、`<0.5GB` は INCONCLUSIVE から A/E へ進む、という運用にするとノイズに強くなります。

- [Suggestion] peak RSS だけでなく phase marker RSS を取るべきです。  
  `after lane load`、`after holdout load`、`after aux pair load`、`GA start` の各点を記録すると、C3 collider bias を避けやすくなります。単一の run peak だけを見ると、別フェーズのピークに条件づけてロード改善を見誤る可能性があります。

**追加確認点への回答**

1. SR-9 の3行要約は十分です。worker recycle は main に効かず、EquityCurve numpy 化は backtest hot path 対象で、どちらも pre-GA DB load に介入しない、という因果整理は妥当です。

2. H1/H2 の関係は概ね妥当です。H1 は最低成功仮説、H2 は期待レンジなので、`0.5〜1.0GB` は「H1達成・H2未達の部分成功」で扱えばよいです。`>2GB` は H2 上振れであり失敗扱いにしない、と一文足すと誤読が消えます。

3. Stop/Go 閾値は、`0.5GB` 判定だけ n≥3 に上げるのがよいです。5秒間隔の RSS sampling で 0.5GB 差を n=1 判定するのは弱いです。一方、`≥1.0GB` はこの施策の目的に対して十分大きい差なので、単発 smoke の合格目安として許容できます。