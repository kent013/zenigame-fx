**Must-fix（最重要3件）**
1. `ensure_registered` の冪等性が競合時に破れる  
`try: get_primitive -> except KeyError: register` は非原子的で、同時呼び出し時に `register` 側で `ValueError` が発生しえます。  
修正案: `_registry.py` に「lock内で存在確認＋登録」を行う `register_if_absent` を追加し、それを使う。少なくとも `ensure_registered` 側で duplicate `ValueError` を握りつぶして冪等化する。

2. F6 `session_open_close` が時系列ギャップで古い値を保持する  
現設計は「前barが非session、当barがsession」のときしか open を更新しないため、週末/欠損/粗い足で「前barもsession判定」のまま日をまたぐと open が更新されません。  
修正案: 「session開始検知」を隣接バー遷移依存にしない。`session_key`（例: 対象session + セッション営業日）を持ち、key変化時に必ず open を再設定。

3. F5 の `short_n < long_n` を compute内で sort/swap する方針  
これは genotype→phenotype を多対一にし、GA探索空間を歪めます（同じ表現型に多数の遺伝子が潰れる）。「名前の役割（short/long）」ともズレます。  
修正案: computeでは並べ替えず、生成/デコード段階で順序制約を課す（または無効個体として低fitness）。

**Should-consider**
1. F6 の UTC固定セッション境界（Tokyo 00-09, London 07-16, NY 12-21）は London/NY のDSTで実市場時刻と季節的にズレます。意図仕様なら明記し、将来は IANA timezone ベースに拡張余地を残す。  
2. F13 warmup は `corr[:lag+w]=nan` だと1本ぶん保守的です（理論上は最初の有効点は `lag+w-1`）。バイアスではないが有効サンプルを1本失う。  
3. F13 の `nan->0` 埋めは、先頭以外に NaN が混入した場合に相関を歪めます。将来の欠損耐性まで考えるなら「有効ペア数ベース」で相関を出す実装が安全。  
4. Wilder系（EMA/ATR/RSI/ADX）の seed を詳細化した方がよいです。seed定義を曖昧にすると実装差で warmup/再現性がぶれます。  
5. `rolling_max/min` の O(N) 保証を明文化（monotonic deque）しておくと、F3/F11 の性能退行を防げます。  
6. `compute_single` の NaN吸収を常時 `0.0` にすると不具合の検知性が落ちます。デバッグ時だけ警告ログを出す運用が有効です。  
7. `bar.complete` の扱いが未規定です。未完バーを使うか除外するかを明記しないと、バックテストと実運用で挙動差が出ます。

**Nit**
1. F14 の次元整合（`rv` 無次元 × `close` で価格次元化）は妥当です。  
2. `required_data=("ohlc",)` は `_REQUIRED_DATA_LITERALS` に合致しており契約上問題ありません。  
3. `_EPS = 1e-10` は FX価格スケールでも数値安定として実用範囲です（極端なゼロ除算回避目的として妥当）。

**判定**
**NEEDS_REVISION**  
（上記 Must-fix 3件を先に潰せば、lookahead/O(N)/型契約の観点で実装に進める状態に近づきます。）