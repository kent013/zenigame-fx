# Old Rounds 1-10 (前提誤り隔離)

**この議論は実装根拠としては無効**です。

## 経緯

2026-04-28〜29 に Codex (gpt-5.4 / xhigh) と 10 ラウンドの cascade port 議論を行ったが、 議論中に複数の前提が「現状 default を hard constraint」 と扱う**前提誤り**で組み立てられていることがユーザ指摘で判明:

- pop_size = 40 (default.yaml 既定値だが議論では fixed constraint 扱い)
- generations = 15 (同上)
- max_workers = 2 (同上)
- canonical 5 の win_rate は単一通貨ペアでは意味がない (graduation lane Phase 4 で zenigame-faithful な意味を取り戻すことを見落とし)
- 計算時間を逆ピラミッドの現状実装から線形外挿していた

## 隔離理由

Round 1-10 の確定事項のうち以下は前提誤りで結論が変わるため、 直接実装根拠にしてはいけない:

- **論点 3 (CPPS scope)**: 「軽量 CPPS」 採択 → fresh で「CPPS フルポート (exec_floor 除く)」 に転換
- **論点 5 (Loop closure)**: pop=40 ベースの hyper-parameter 全て → pop=192 baseline で再校正必要
- **論点 2 (canonical 5)**: profit_factor 採用 → fresh で win_rate 維持 (session_block_win_rate に semantic 上げ)
- **論点 1 (dataset)**: 24 ヶ月延長を「データ取得が必要」 と誤認識 → DB に既に 3 年分あった
- **適用順序**: 旧 Phase 構成 → fresh で Contract 固定優先に再構成

## 残す価値

- **誤読パターン記録**: 「config default を hard constraint と扱った」 「単一通貨ペアの semantic 誤解」 「現状実装から compute 外挿」 という 3 つの誤りパターンを記録、 同種誤り再発防止の監査ログ
- **議論プロセス documentation**: Codex セッションのラウンド進行の記録として、 思考原則の C4 (前提検証) C9 (反証先行) discipline 違反例

## 正しい議論

`devnotes/20260428-2300-cascade-port-debate/round-11.md` 以降の fresh 議論と `synthesis.md` を参照すること。
