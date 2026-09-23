# 詳細設計: Run 85 施策（P2: Stage C stress の cost-robustness 化）

## 使命・制約（絶対遵守）
- 使命: live_criteria 全達成個体を見つける。達成後は閾値引き上げ（緩和禁止）。
- FX 制約: イントラデイ前提 / ロング・ショート両方向 / スワップ・スプレッド控除後純益。
- **default 挙動不変が絶対条件**: spread_cost_multiplier=1.0（default）で Stage A/B/base-C の全 backtest は完全に現行同一。stress 経路のみ >1。

## 施策一覧
| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| P2 | Stage C stress の cost-robustness 化 | src/broker/mock.py, src/backtest/engine.py, src/alpha_factory/stage_gate.py | 全 live_criteria の妥当性（cost robust 個体のみ Stage C 通過） |

## P2 詳細

### target_metric / failure_mode / causal_path / falsification / success_criterion
- target_metric: stress_pnl_degradation 分布（非ゼロ化）、stress 下の Stage C 通過個体数。
- failure_mode: 現行 Stage C stress は max_spread_bps（spread フィルタ閾値）を 1.5 倍に緩めるだけで per-trade コストを増やさず、stress_pnl_degradation 全個体 0（cost robustness 未検証）。
- causal_path: broker fill 時に実効スプレッドを multiplier 倍に広げる（adverse 方向へ (m-1)×half_spread 上乗せ）→ 往復取引コストが m 倍 → cost 増が PnL に反映 → cost fragile 個体は stress で PnL 悪化 → 真に cost robust な個体のみ stress gate 通過。
- falsification: P2 導入後も stress_pnl_degradation が 0 のまま → 配線/実装不整合。
- success_criterion: R85 で stress_pnl_degradation が多数個体で >0、stress 下 Stage C 通過が cost robust 個体に限定。

### 現状の事実（調査済）
- fill は bid/ask 約定: long entry=`bar.ask.open`, short entry=`bar.bid.open`（mock.py:232,241）、long exit=`bar.bid.{open,close}`, short exit=`bar.ask.{open,close}`（mock.py `_exit_price`）。spread は fill で自然発生。
- `max_spread_bps` は `set_spread_filter`（spread>閾値 の trade を reject するフィルタ、mock.py:165-208）であり cost ではない。
- `_compute_trade_spread_cost`（mock.py:436-460）は往復 spread cost（2×exit_spread）を**記録のみ**（PnL 未反映、line 439 明記）。
- Stage C stress（stage_gate.py:1950-1996）は `replace(backtest_config, max_spread_bps=new_max)` で **フィルタ閾値のみ** 1.5 倍 → cost 不変 → degradation=0。

### 変更箇所

#### (1) `src/backtest/engine.py` — BacktestConfig に spread_cost_multiplier 追加
```python
@dataclass(frozen=True)  # 現行の dataclass 装飾に合わせる
class BacktestConfig:
    ...
    max_spread_bps: Decimal | None = None
    holding_cost_per_day_bps: Decimal = Decimal("0")
    # P2: stress 用 spread コスト倍率。default 1.0 = 現行挙動不変。
    # >1.0 で fill 実効スプレッドを倍率分 adverse 方向へ広げ、cost robustness を stress する。
    spread_cost_multiplier: Decimal = Decimal("1.0")
    ...
```
- `__post_init__` に検証追加: `if self.spread_cost_multiplier < 1: raise ValueError(...)`（1.0 未満禁止 = cost を減らす方向は不許可）。
- `run_backtest`（engine.py:169 付近、`broker.set_spread_filter(config.max_spread_bps)` の隣）で `broker.set_spread_cost_multiplier(config.spread_cost_multiplier)` を呼ぶ。

#### (2) `src/broker/mock.py` — **realized fill のみ** に multiplier を適用（MTM/margin は生価格）
**契約（Codex Round 1 [Critical] 反映）: stress は realized fill (entry/exit 約定) のみに適用。mark-to-market / margin 判定は両経路とも生価格を使う。** → `_exit_price` を一括 multiplier 化しない（MTM の `_unrealized_pnl` が同関数を使うため parity が壊れる）。realized fill の呼出点でのみ補正する。
- `__init__` に `self._spread_cost_multiplier: Decimal = Decimal("1.0")` 追加。`set_spread_cost_multiplier(self, m: Decimal)`（検証 m>=1）。
- **entry fill**（fill_pending 内、mock.py:232/241、realized）:
  - long entry: `eff = bar.ask.open + adj_open`、short entry: `eff = bar.bid.open - adj_open`
- **realized exit fill**（現行メソッド名 `_close_one` 内、mock.py:404 の `exit_price = self._exit_price(...)` の直後で realized 用に補正。Codex Round 2 指摘で `_close_position` でなく `_close_one`）:
  - long exit: `eff = raw_exit - adj`、short exit: `eff = raw_exit + adj`
  - `raw_pnl = self._realized_pnl(pos, eff)` に eff を渡す。
- **MTM（`_unrealized_pnl`, mock.py:483）は raw（`_exit_price(...,"close")` 生値）のまま** — 一切変更しない。margin call 判定も生価格。
- **adj 計算（丸め規約、Codex [Suggestion] 反映）**: 必ず非負の `spread_diff = max(0, ask - bid)` から計算し、符号は side で最後に適用。
  `adj = (m - 1) * spread_diff / 2`（= (m-1)×half_spread）。負数除算を使わない。bid>ask 異常時 spread_diff=0 → adj=0。
- m=1.0 → adj=0 → realized fill も現行と完全同一。

#### (2k) `src/broker/mock.py` の二重: 上記は MockBroker。kernel は (1k) 参照。

#### (3) `src/alpha_factory/stage_gate.py` — stress 経路で multiplier を設定
- stress 経路（現行 1950-1955 付近）の `stress_config = replace(backtest_config, max_spread_bps=new_max)` を
  `stress_config = replace(backtest_config, spread_cost_multiplier=Decimal(str(stage_config.spread_stress_multiplier)))` に変更（max_spread_bps の緩和は廃止 or 併用は設計判断 — **推奨: max_spread_bps はそのまま、spread_cost_multiplier を追加設定**。フィルタ緩和は副作用なので stress では filter は base のまま据え置き、cost のみ stress）。
- `spread_stress_multiplier`（既存 default 1.5、stage_gate.py:582）を流用。
- stress_payload の pnl_degradation = base_total_pnl - stress_total_pnl が cost 増を反映して非ゼロ化。

### 波及変更（AGENTS.md / skill / config / docs）
- config: BacktestConfig に新フィールド。`config/alpha_factory/default.yaml` に spread_cost_multiplier の明示はなし（default 1.0、stress 内部設定のため）。docs に stress 意味論の更新。
- AGENTS.md: GA 引数 / CLI 変更なし → 不要。
- docs: `docs/alpha_factory/stage-gates.md` の Stage C stress 記述を「フィルタ緩和→コスト割増」に更新。

### ルックアヘッドバイアスチェック（fill 価格変更 = backtest ロジック、primitive ではないが準じて確認）
- [ ] 未来バー参照なし（fill は当該 bar の ask/bid のみ使用、現行同様）
- [ ] half_spread は同一 bar の ask-bid（因果的）
- [ ] m=1.0 で現行と数値同一

### ★★ 重大: fill 経路は 2 つ（kernel + MockBroker）— 両方の改修が必須 ★★
調査確定（src/backtest/engine.py:140-159, src/backtest/_sim_kernel.py）:
- **① numba kernel 経路** `_sim_kernel.simulate()`: `_can_use_kernel` 成立時に使われる高速経路（T108、最近マージ）。**R83/R84 は engine=kernel で実行されており、本番で実際に使われるのはこちら**。fill は `out_entry_px`/`out_exit_px` に bid/ask 配列（PRICE_SCALE 整数化）で出力。
- **② Decimal/MockBroker 経路** `_run_backtest_decimal()`: kernel preflight 不成立/overflow 時の fail-safe。
- **P2 は両経路に spread_cost_multiplier を配線必須**。kernel 経路だけ漏らすと、本番（engine=kernel）では stress が依然 toothless（degradation=0）= falsification 条件に直撃。
- kernel 改修の難所: (a) `simulate()` の njit シグネチャに multiplier を **整数比 (m_num, m_den)** で追加（例 3/2）、(b) 整数 PRICE_SCALE 空間で realized fill のみ補正、(c) m_num=m_den で**ビット同一**保証、(d) entry/exit の long/short 符号。

#### (1k) kernel realized fill 補正（_sim_kernel.simulate、realized のみ・MTM 生価格）
**realized close は signal close だけでなく全強制決済分岐を網羅必須（Codex Round 2 [Warning] 反映）。** njit 内 helper（小関数 or インライン）で entry/exit を補正。補正対象 realized fill の全分岐:
- **entry**（常に open 価格）: long `pos_entry=ask_o[i]`(L185) → `+adj_o`、short `pos_entry=bid_o[i]`(L194) → `-adj_o`。`adj_o=((m_num-m_den)*max(0,ask_o[i]-bid_o[i]))//(2*m_den)`。
- **exit ①signal close**（open 価格、L203/206）: long `bid_o[i]-adj_o`、short `ask_o[i]+adj_o`。
- **exit ②margin_call close**（close 価格、L250/253）: long `bid_c[i]-adj_c`、short `ask_c[i]+adj_c`。`adj_c=((m_num-m_den)*max(0,ask_c[i]-bid_c[i]))//(2*m_den)`。
- **exit ③session/EOD close**（close 価格、L272/275）: long `bid_c[i]-adj_c`、short `ask_c[i]+adj_c`。
- **exit ④ループ後 end-of-run 強制 close があれば同様に補正**（実装時に simulate 末尾の残ポジション決済有無を確認し、あれば close 価格で補正）。
- pnl 計算（pnl_factor*(exit_px-pos_entry) 等）は補正後の pos_entry/exit_px を使う（realized PnL に cost 反映）。
- **MTM/margin の unreal（L167-170 / L231-234 の bid_c/ask_c）と margin RHS（L247 の pos_entry）は生価格のまま変更しない**。ただし margin RHS の pos_entry は「実約定 entry 価格（補正後）」を使う点に注意 = entry は realized なので補正後 pos_entry が入る（MTM の unreal 価格 bid_c/ask_c のみ raw、entry 約定値は realized で補正済が正）。→ 契約: 「unrealized 評価に使う当 bar 価格(bid_c/ask_c)は raw、約定 entry/exit 価格は補正後」。
- adj 計算（整数、非負 spread_diff から、符号は side で最後）:
  - entry 時: `spread_diff_o = ask_o[i] - bid_o[i]`（preflight で ask>=bid 保証だが `if <0: 0`）。`adj_o = ((m_num - m_den) * spread_diff_o) // (2 * m_den)`。
  - long entry: `pos_entry = ask_o[i] + adj_o`、short entry: `pos_entry = bid_o[i] - adj_o`。
  - exit 時: 同様に `adj = ((m_num - m_den) * (ask_o[i]-bid_o[i])) // (2*m_den)`。long exit: `exit_px = bid_o[i] - adj`、short exit: `exit_px = ask_o[i] + adj`。
- `m_num=m_den=1` → `(m_num-m_den)=0` → `adj=0` → **整数演算でビット同一**（floor 除算も 0//k=0）。
- 丸め: 非負 `(ask-bid)` から floor 除算 → long/short とも adj>=0、符号適用後は両側 adverse。負数 floor 除算を使わないため long/short 非対称な不利が出ない（Codex [Suggestion] 反映）。
- `_can_use_kernel` / `_run_backtest_kernel`（engine.py）で config.spread_cost_multiplier を (m_num,m_den) に分解して simulate へ渡す。Decimal → 整数比変換は既存 max_spread の num/den 変換（engine.py:365-370）と同型。
- 実装順序推奨: まず MockBroker（②）で設計検証 → kernel（①）に同ロジック移植 → 両経路の数値一致テスト（同一 genome で kernel と decimal が一致、かつ m=1.0 で現行一致）。

### パフォーマンスチェック
- fill ごとに定数演算 1-2 個追加のみ。無視可能。**kernel 経路（njit）への配線が本質**（上記）。njit 内なので Python オブジェクト生成禁止、整数演算のみ。

### テスト計画
- [ ] **数値同一性**: spread_cost_multiplier=1.0 で既存 backtest の trades/PnL が現行と完全一致（regression、最重要）。
- [ ] multiplier=1.5 で long/short entry/exit の実効 fill 価格が adverse 方向へ (m-1)×half_spread 移動することを単体検証。
- [ ] multiplier=1.5 で往復 spread cost が約 1.5 倍、PnL が spread 分悪化することを検証。
- [ ] bid>ask 異常時に half_spread が負にならず clamp されること。
- [ ] BacktestConfig.__post_init__ が spread_cost_multiplier<1 を reject。
- [ ] stage_gate stress 経路が spread_cost_multiplier を設定し、stress_payload.pnl_degradation が非ゼロ化する integration test。
- [ ] **kernel-vs-decimal parity (m>1)**: 同一 genome で m=1.5 を kernel 経路と Decimal 経路に適用し、trade 列・exit_reason・realized PnL が一致すること（Codex Round 1 必須追加）。
- [ ] **MTM/margin parity (m>1)**: m=1.5 で margin 境界ケースでも kernel/Decimal の exit_reason が一致（MTM は生価格契約の検証）。
- [ ] m=1.0 で kernel/Decimal 双方が現行とビット同一（既存 parity test regression）。

### リスク
- **中**。fill 価格は全 PnL に直結。default 1.0 で挙動不変だが、kernel engine 経路への伝搬漏れがあると stress が依然 toothless（degradation=0）になる → falsification 条件に直結。実装時に kernel/MockBroker 二重経路を必ず両方配線。
- _exit_price の staticmethod→instance 化で呼び出し元更新漏れに注意。

## Run 85 実行パラメータ
| パラメータ | 値 | R84 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 不変 |
| population-size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation-rate | 0.5 | 不変 |
| seed | 68 | R83 と同 seed（mission 達成 seed で P2 適用後に cost robust 個体が残るか検証） |
| max-workers | 2 | 不変 |
| stage-b-gate-kind | profit_safe_pfr | 不変 |

> seed=68 を選ぶ理由: R83（seed=68）で 43 mission 個体が出た。P2（真の cost stress）適用後に、これらが cost robust で生き残るか / cost fragile で脱落するかを直接観測できる（P2 の効果が最も明確に出る seed）。

## Codex design-review: APPROVED (Round 2)
realized fill のみ補正 / MTM・margin 生価格 / 全 close 分岐網羅 / 整数比 m=1.0 ビット同一。

## ★ impl-review Round 1 [Critical] 修正中（Option A への切替）
**問題**: 初回実装は entry 補正で pos_entry / Position.entry_price 自体を adverse 化したが、その値が MTM(unrealized PnL) と margin RHS にも使われるため「MTM/margin は生価格」契約に違反（m=1.5 で margin 挙動が m=1.0 と変わる）。parity(kernel=decimal)は保持されるが契約違反 + pnl_degradation に margin タイミング変化が交絡。

**修正方針 Option A（採用）**: 
- entry/exit は **MTM/margin 用に raw を保持**（kernel: pos_entry=raw ask_o/bid_o、MTM L167-170/L231-234・margin RHS L247 は raw のまま＝編集不要に戻す。MockBroker: Position.entry_price=raw、_unrealized_pnl は raw のまま）。
- **realized PnL からのみ往復 stress cost を控除**: stressed_pnl = raw_directional_pnl - pnl_factor*(entry_adj + exit_adj)。entry_adj は entry bar の _fill_adj、exit_adj は close bar の _fill_adj。pnl_factor は正の units*scale。
- **trade 記録 (out_entry_px/out_exit_px, Trade.entry_price/exit_price) は stressed fill** を記録（entry: raw±entry_adj、exit: raw∓exit_adj）。
- kernel: pos_entry_adj を entry 時に保持する scalar を追加。各 realized close で exit_adj 計算 → cost 控除 + stressed px 記録。MTM/margin 行は触らない（raw pos_entry 使用）。
- MockBroker: Position に entry_stress_adj field 追加（or entry_raw/entry_fill 分離）。_close_one で raw entry/exit から cost 控除、Trade に stressed px 記録。_unrealized_pnl は raw entry のまま。
- **追加テスト必須**: m=1.0 vs m=1.5 で margin_call 発火タイミング・exit_reason 列が不変であること（MTM/margin invariance 直接検証、impl-review [Critical] 反証仮説）。
- m>1 で realized PnL 悪化・kernel=decimal parity は維持（既存新規テスト継続）。
