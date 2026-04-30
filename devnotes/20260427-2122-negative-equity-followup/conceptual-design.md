# 概念設計: negative equity 再発の根本修正（OANDA 準拠強制ロスカット + fill_pending 余力 gate）

## 0. 前提検証表

| # | 前提 | 状態 | 根拠 |
|---|---|---|---|
| P1 | 本番 RUN で `trade_return.invalid_equity_at_entry equity_at_entry=-9.7M` warning が連続 trade_position_id で発生 | **verified** | 2026-04-27 21:13 のユーザー観測 log |
| P2 | T049（closed 済み）で `force_close_if_margin_call` が `mock.py:278` に追加済み、`maintenance_pct=100%` で発火 | **verified** | コード grep |
| P3 | `_open_position`（mock.py:312）には cash / equity / margin 余力チェックが**完全に存在しない** | **verified** | コード読解 |
| P4 | `fill_pending`（mock.py:175）も `pre_fill_equity = self._snapshot_at(bar).equity` を取って **そのまま open**（負値でも進行） | **verified** | コード読解 |
| P5 | leverage は 2026-04-27 commit `a255338` で 25 → 3 に変更済み | **verified** | git log |
| P6 | 本変更は数値計算には触らず、broker 状態の事前 gate のみ追加 | **verified** | 設計上 |
| P7 | force_close_if_margin_call は **保有 0 → margin_used = 0 → 早期 return** で何もしない（mock.py:281） | **verified** | コード読解 |
| P8 | OANDA v20 仕様: `marginCloseoutPercent ≥ 1.0`（=維持率 100% 以下）で margin closeout 発動、全 position 成行決済 | **verified** | context7 `/websites/developer_oanda_rest-live-v20` |
| P9 | 現状実装の `maintenance_margin_level_pct=100` は OANDA Japan の強制ロスカット閾値と一致 | **verified** | OANDA spec 確認 + コード読解 |
| P10 | 現状実装の `_close_all_internal(reason="margin_call")` は OANDA の「全 position 成行決済」と整合 | **verified** | OANDA spec 確認 + コード読解 |

## 1. 背景・課題

### 1.1 観測事実（Facts）

run-25（2026-04-27 21:13）log に `trade_return.invalid_equity_at_entry equity_at_entry=-9702420.000000 trade_position_id=34938`, `equity_at_entry=-9702400.000000 trade_position_id=34939`, ... のように **連番 trade_position_id** で連続して発生。

equity が **-970 万**（initial_cash=100 万 JPY の約 -10 倍）まで爆発。

T049（`negative-equity: negative equity warnings 調査 + ストップアウト logic 整備`）が 2026-04-27 10:22 に Closed としてマークされているが、**症状が再発**している。

### 1.2 原因仮説（Interpretation）

T049 のストップアウト logic は「**保有中 positions の margin level 監視**」を治しただけで、**保有ゼロ + cash マイナス状態で新規 open する経路**は塞がれていない:

1. 過去の loss で realized loss 累積 → cash 大幅マイナス
2. `force_close_if_margin_call` は保有 0 → `margin_used = 0` → 早期 return（mock.py:281）→ 何もしない
3. `strategy.on_bar` が open_long シグナル発信（GA は equity の負を知らない）
4. `submit` → pending
5. 次 bar の `fill_pending` → `_open_position` → **チェックなし → open 成功**
6. `trade.equity_at_entry = -970 万` が記録される
7. metrics で warning が大量発生

つまり「破産後も延々と新規 open し続けられる」のが残存バグ。

### 1.3 leverage 25→3 の前段措置との関係

直前 commit `a255338` で `backtest.leverage: 25 → 3` に変更済み。これにより 1 trade の損益振れ幅が約 1/8 に縮小し、**破産経路に入る速度**は遅くなる。しかし「破産後の雪だるま」の構造そのものは leverage 変更では塞がれない（破産確率の母数を減らすだけ）。本 TODO は **fail-closed re-entry block** で構造的に経路を閉じる。

---

## 2. 改善アイデア

### 2.0 OANDA 準拠強制ロスカット仕様の整理（既存実装の文書化）

OANDA v20 / OANDA Japan の強制ロスカット（margin closeout）仕様:
- 維持率（NAV / 必要証拠金）が 100% 以下になった時点で発動
- 発動時は**全保有 position を成行で順次強制決済**（OANDA は最大ロットから順、本実装は全閉じ＝相当する）
- OANDA-Japan は JFSA 規制下で同等仕様（破産防止のため retail 顧客に必須）

現状実装（mock.py:278 `force_close_if_margin_call`）は上記に概ね準拠:
- ✅ 閾値: `maintenance_margin_level_pct=100`
- ✅ 発動時挙動: `_close_all_internal(reason="margin_call")`
- ✅ 発注価格: 当該 bar の bid/ask（成行相当）
- ✅ engine.py:150 で per-bar 呼び出し

**OANDA spec 準拠の確認のみ**（本 TODO のスコープ）:
- C1. ドキュメント `docs/alpha_factory/runbook.md` に「OANDA 準拠の margin closeout 設計（既存）」セクションを追加し、再認識のための記録

**Round 1 [Suggestion] 反映**: `maintenance_margin_level_pct` の config 化は本 TODO の本質ではないため**別 TODO に分離**（negative equity 再発の根本因は open gate 欠如であり、threshold config 化は独立変更。1 PR に混ぜると検証面が広がる）

ただし本変更だけでは run-25 で観測された **equity_at_entry=-970万** 問題は解決しない。問題の本質は「保有 0 + cash マイナス時の新規 entry を止める仕組みが無い」（P3 / P4 / P7）であり、これは OANDA spec と独立した構造的バグ。

### 2.1 fill_pending 余力 gate（本 TODO の主軸）

`fill_pending` 冒頭に **equity 余力 gate** を追加し、`equity <= 0` なら **open 系 pending を全 drop**（既存 `drop_pending_open` の session_close パターンを踏襲）。

### 2.2 設計判断 — なぜ fill_pending 層か

候補と比較:

| 案 | 場所 | メリット | デメリット |
|---|---|---|---|
| **A: fill_pending での equity gate**（採用） | `mock.py:175` 冒頭 | 既存 `drop_pending_open` パターンと整合、fail-closed 明示、テスト容易、submit 後に状況変化した場合も対応 | 1 layer 下流で gate するため strategy 側は equity を意識しない設計のまま（むしろ責務分離として正しい） |
| B: `_open_position` での fail-fast | `mock.py:312` 内 | 最終 gate として強い | 呼び出し側 `fill_pending` のループ内で個別 skip するか全 abort かの判断が必要。設計が曖昧化 |
| C: `DslStrategy.on_bar` での出力ブロック | `dsl/strategy.py` | 上流で止められる | strategy 層が broker の cash 状態を直接知る必要、契約が壊れる |

→ **案 A** が最もクリーン。

### 2.3 実装スケッチ（多層防御: Round 1 [Warning] 反映）

**Round 1 反映**: 単一層では薄いため **多層防御**にする:
1. **L1 (主)** `fill_pending` 冒頭で **fail-closed gate**: equity が非有限値 or `<= 0` なら open 系 pending を全 drop
2. **L2 (最終防御)** `_open_position` 内で **defensive check**: `equity_at_entry` が非有限値 or `<= 0` なら open 拒否（domain-specific exception で fail-fast。L1 を通り抜ける経路があれば即発覚）

**Round 1 反映**: 非有限値（NaN / Infinity）を `<= 0` 比較に通すと `Decimal('NaN') <= 0` で `InvalidOperation` を起こすため、**`equity.is_finite() and equity > 0` のときのみ open 許可**（fail-closed）。

**Round 1 反映**: 同 bar 内の strategy.on_bar が close signal を出し equity 復活する直前の bar で open を drop する可能性 → これは **意図的に conservative policy として採用**（同 bar 内 recovery を取り逃がすが、fail-closed として許容、設計に明記）。

```python
# src/broker/mock.py: fill_pending 冒頭
def fill_pending(self, bar: PriceBar) -> list[Trade]:
    if bar.pair_name != self._meta.oanda_name:
        raise ValueError(...)

    pre_fill_equity = self._snapshot_at(bar).equity

    # L1: equity の非有限値 / 非正値での open 系 drop（fail-closed）
    # 注: 同 bar 内の close signal による equity recovery は意図的に取り逃がす
    # （fail-closed policy として明文化、設計 §2.3 参照）
    if not _is_finite_decimal(pre_fill_equity) or pre_fill_equity <= Decimal(0):
        before = len(self._pending)
        self._pending = [
            (sig, lev) for (sig, lev) in self._pending
            if sig.kind not in ("open_long", "open_short")
        ]
        self._negative_equity_drop_count += before - len(self._pending)
        # log は出さない（T055 と同じ方針）

    # 既存の spread filter（後段）はそのまま
    ...
```

```python
# src/broker/mock.py: _open_position L2 最終防御
def _open_position(self, ..., equity_at_entry: Decimal) -> Position:
    # L2: defensive guard（L1 を通り抜ける経路があれば fail-fast）
    if not _is_finite_decimal(equity_at_entry) or equity_at_entry <= Decimal(0):
        raise InsufficientEquityError(
            f"_open_position called with non-finite or non-positive equity: {equity_at_entry}"
        )
    # 既存ロジック（notional / margin 計算 + position 生成）
    ...
```

`InsufficientEquityError` は新規 domain exception。

**Round 2 [Warning] 反映: L2 例外の捕捉設計を明確化**

`fill_pending` のループ内で **個別 signal 単位で try/except** し、`InsufficientEquityError` をキャッチ→ `negative_equity_drop_count += 1` して**当該 signal だけ skip し、ループは継続**する（fail-closed を「停止」ではなく「拒否」に統一）。これにより:
- L1 を通り抜けて L2 が発火しても bar 処理は中断しない
- pending クリア漏れも発生しない（catch 後に該当 signal は drop 扱いとして処理される）
- 正常な close 系 signal（同 bar 内）は影響を受けず実行される

```python
# fill_pending ループ内 (L2 例外の握り)
for signal, leverage in self._pending:
    if signal.kind == "open_long":
        try:
            self._open_position("long", ..., equity_at_entry=pre_fill_equity)
        except InsufficientEquityError:
            self._negative_equity_drop_count += 1  # L1 を通り抜けたケース
            continue  # bar 処理は止めない
    elif signal.kind == "open_short":
        try:
            self._open_position("short", ..., equity_at_entry=pre_fill_equity)
        except InsufficientEquityError:
            self._negative_equity_drop_count += 1
            continue
    elif signal.kind == "close_position":
        # close 系は影響を受けず通常処理
        ...
```

`run_backtest`（engine.py）側:
- `n_dropped_negative_equity` を per-call で集計（broker から戻り値で返す or counter accessor）
- `backtest.finished` log に `negative_equity_drop_open_count` field を追加（T055 の集計パターン踏襲）

### 2.4 broker → engine の通信方式

選択肢:
1. `fill_pending` の戻り値に「drop 件数」を追加（型変更を避けるため tuple 化）
2. `MockBroker` に `pop_negative_equity_drop_count()` メソッドを追加（counter accessor 型、**pop semantics**）
3. `BacktestResult` ではなく log 経由（per-bar log は T055 で削除済みのため再導入は方針に反する）

→ **案 2** が API 互換性高い（既存 `fill_pending` 戻り値型 `list[Trade]` を維持）。

**Round 1 [Suggestion] 反映**: counter は **pop semantics** にする（`pop_negative_equity_drop_count()` を呼ぶと内部 counter が 0 にリセット）。複数 backtest や再利用時の混線を防ぎ、**「per-fill_pending での累計」ではなく「pop 呼び出し以降の累計」契約**にする。`run_backtest` は backtest 完了時に 1 回 pop して `backtest.finished` log の `negative_equity_drop_open_count` field に渡す。

---

## 3. 期待効果

### 3.1 機能目標（必須）

- equity_at_entry < 0 の trade が **構造的に発生しなくなる**（fill_pending で drop されるため）
- 観測: warning が「適切な量」（数件以下、もしくはゼロ）に収まる
- backtest 結果の妥当性が回復、Stage A/B/C fitness の信頼性向上

### 3.2 副次効果

- 破産後の GA 個体は trade を出せない → fitness 低下 → 自然淘汰
- T049 / T053 / T054 / T055 と組み合わせて pipeline 全体が機能する状態に近づく

### 3.3 性能目標（INCONCLUSIVE）

事前見積りなし。実装後 RUN で wall-clock を実測（破産個体は trade 0 で早期終了するため、本番 RUN time 短縮の副次効果が期待できる可能性がある）。

### 3.4 使命への貢献

- 直接的な live_criteria 数値操作なし（fail-closed gate の追加）
- 評価 pipeline の妥当性を回復させる
- 破産個体を構造的に淘汰する（GA の探索効率向上 → 使命達成への到達経路改善）

---

## 4. 制約・前提

### 4.1 数値・絶対制約

- 本変更は **broker 状態の事前 gate**のみで、composite / primitive / 数値計算には触らない
- T053 / T054 / T055 の数値同値性検証結果を破壊しない（破産しない genome の trade は完全一致、破産する genome は trade が出なくなるが、それは「破産個体」であり本来淘汰されるべき）
- イントラデイ / ロング・ショート両方向 / swap・spread 反映は不変

### 4.2 後方互換

- `MockBroker.fill_pending` の戻り値型 `list[Trade]` を維持（counter accessor 型を採用）
- `backtest.finished` への新 field 追加は schema 拡張（既存 consumer は ignore できる）
- 既存テストで「破産シナリオで trade が出ること」を assert しているテストがあれば、それは「破産個体は trade 出さない」契約に更新（破産シナリオの test 仕様 review 必須）

### 4.3 禁止事項の遵守

- live_criteria 緩和なし（禁止 4）
- 評価期間延長なし（禁止 1）
- 取引回数の見せ方変更なし（禁止 6、本変更は「破産個体は取引できない」自然な結果）
- GA ハックなし（禁止 3、broker 層の物理制約強化）

---

## 5. スコープ外（将来 TODO 候補）

**Round 2 [Suggestion] 反映**: OANDA 準拠の更なる拡張は別 TODO で扱う:
- `available_margin >= required_margin` gate（過大 notional の entry reject）
- `maintenance_margin_level_pct` の config 化

### 本 TODO のスコープ外

- T049 既存ストップアウト logic の再設計（保有中の margin level 監視は機能している前提）
- per-trade warning ログの抑制（ユーザー方針: 適切な量なら不要）
- swap / spread / leverage パラメータの調整（leverage は別 commit `a255338` で 25→3 完了済）
- live_criteria 閾値そのものの調整
- Cross-pair (ii-lite) 評価系

---

## 6. 検証計画（概要、詳細設計で具体化）

| # | 項目 | 合格基準 |
|---|---|---|
| V1 | 既存テスト全パス | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ tests/broker/ -x` |
| V2 | 数値同値性 | 同一 seed / config / bars で「破産しない genome」の trade / equity_curve / final_equity が baseline と完全一致 |
| V3 | 破産シナリオ test | equity が負になる sequence で fill_pending が open 系 pending を全 drop し、`negative_equity_drop_open_count` が正しく集計される |
| V4 | warning 件数の劇的減少 | 実 RUN ログで `trade_return.invalid_equity_at_entry` が消えるか「適切な量」に収まる |
| V5 | ruff / mypy | `uv run ruff check src/ tests/` PASS, `uv run mypy src/` PASS |
| V6 | broker → engine 通信 | counter accessor 経由で drop 件数が正確に伝搬する unit test 追加 |
