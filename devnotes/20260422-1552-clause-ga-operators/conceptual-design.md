# Conceptual Design: Clause-aware GA operators + complexity penalty (T008)

**作成日時**: 2026-04-22 15:52 (JST) / **Round 2 改訂**: 16:20 (JST)
**前提 TODO**: T007 clause-genome-structure（APPROVED / merged: commit aa0dfbb）
**後続 TODO**: T009 clause-backtest-integration、T010 primitives-registry

## 0. 目的

Clause ベース Genome（SignalConfig × ClauseConfig × PositionConfig × RiskConfig）に対応した
GA 遺伝子オペレータ群を再実装する。

- `random_gen`: Clause 構造の初期個体をランダム生成
- `crossover`: 実行可能な operator 集合から**一様選択**（Clause-level / Signal-level / gate swap / config swap）。
  将来的に operator ごとの重み付け拡張可能性を残すが、本 TODO では一様選択で固定。
- `mutate`: attempted-edits 回数を Binomial で先引きし、mutation kernel を後で割り当て（rate 意味論明確化）。
  attempted-edits 契約であり effective-diffs 保証は提供しない。
- `complexity penalty`: fitness に size_norm ペナルティを加算（bloat 抑制）
- `runner`: Individual / GaResult を Clause 前提に更新、`EvaluationResult` 注入可能な evaluator 契約

全オペレータの出力は `enforce_consistency` を通すが、これは **最終正規化** であり
「構造不変条件は operator が自ら守る」「clip / swap / dedupe は enforce が最終整形」に責務を分離する。

## 1. 仮説と成功条件

### 1.1 仮説

- **H1**: 「実行可能な operator の集合から一様選択」方式の crossover は、`max_clause=1` /
  `local_gate<=1` という構造制約下でも実効的な多様性生成を保証する（Montana 1995 STGP 系譜、
  型/構造を先に守る発想）。operator 重み付けは将来拡張の余地として残すが、本 TODO では一様選択。
- **H2**: mutation rate を「attempted edits 数」として Binomial で先引きすることで、
  `rate=0 → 必ず no-op（0 attempts）`、`rate=1 → K attempts 確定実施`という
  attempted-edits 契約を明確化できる（effective-diffs 保証ではない点を固定）。
- **H3**: `size_norm` ペナルティで fitness 互角個体のうち構造的にシンプルなものを優先選択
  （Luke & Panait 2006 bloat / parsimony pressure）。

### 1.2 成功条件

- `tests/ga/` の 3 module-level skip を解除、全新規テスト pass
- `mypy src/ga/` および `ruff check src/ga/ tests/ga/` クリーン
- operator 直後の `enforce_consistency` は**最終正規化**、構造不変条件は operator が保証
- Codex conceptual-review APPROVED、design-review APPROVED

## 2. 方針決定（Round 1 指摘反映）

### 2.1 Dummy primitive registry の位置づけと docs 整合

**Round 1 指摘**: 既存 `docs/alpha_factory/primitives.md` では registry の category は
`directional / modulator` の 2 値、`local_gate` は primitive 種別ではなく**配置先**。
→ 本設計も docs に合わせる。

```python
@dataclass(frozen=True)
class PrimitiveSpec:
    id: str                                    # PascalCase 一意 ID（primitives.md の name 準拠）
    category: Literal["directional", "modulator"]
    domain: Literal["generic", "pair_specific"]
    param_schema: Mapping[str, tuple[float, float] | tuple[int, int]]
```

- `local_gate` はプリミティブ種別ではなく、`ClauseConfig.local_gate` に配置した
  `SignalConfig` のこと。配置先の意味論を primitive category と混同しない
- `modulator` category の primitive を `local_gate` に配置するのが典型
  （`directional` category を `local_gate` に置くことは禁止しない — enforce は category を
  見ていない、配置責任は random_gen / operator にある）

**配置**: DUMMY_REGISTRY は `src/ga/_dummy_registry.py` に private module として分離。
`src/ga/random_gen.py` 公開 namespace を汚染しない（T010 で正式 registry に置換される前提）。

### 2.2 Crossover 設計（Round 1 指摘反映）

**Round 1 指摘**: 50/50 固定 mix は `max_clause=1` 初期条件で Clause-level swap が不可能、
local_gate point crossover も実質不可能。「実行可能な operator の集合から重み付き選択」に変更。

**新設計**: 実行可能な operator のみを候補集合に入れ、候補から一様選択。

| operator | 前提条件 | 内容 |
|----------|---------|------|
| clause_point | `min(len(A.clauses), len(B.clauses)) >= 2` | 点交叉で clauses を分割・交換 |
| clause_swap | `len(A.clauses) >= 1 and len(B.clauses) >= 1` | 各親から clause を 1 本選び丸ごと swap |
| directional_swap | 両親の対応 clause に `len(directional) >= 2` が 1 組以上存在 | directional tuple の点交叉 |
| gate_swap | 両親の対応 clause の `local_gate` が片方空でない | clause の local_gate tuple を丸ごと swap（point crossover ではなく) |
| position_swap | always | PositionConfig を親選択で swap |
| risk_swap | always | RiskConfig を親選択で swap |

各世代の crossover 呼び出しで:
1. 前提条件を満たす operator 集合を計算
2. 候補から一様選択（1 operator / 呼び出し、子 2 体生成）
3. `crossover_rate > rng.random()` で crossover 適用、否則は両親をそのまま子

**local_gate に関する注**: `enforce_consistency` で local_gate は最大 1 本に圧縮される。
したがって **local_gate の point crossover は設計上意味が無い**（1 要素 tuple の内部分割ができない）。
代わりに「gate_swap」= clause の local_gate を丸ごと swap（A → B の 1 本を入れ替え）を使う。

**候補集合の非空性**: `position_swap` / `risk_swap` が **always** 前提のため、
候補集合は常に非空。**fallback 不要**（Round 2 指摘で parent-choice fallback は削除、
矛盾を解消）。`clause_swap` も両親が Genome である以上 `len(clauses) >= 1` が保証される
ため、`position_swap / risk_swap / clause_swap` の 3 つは常に利用可能。

### 2.3 Mutate 設計（Round 1 / Round 2 指摘反映）

**Round 1 指摘**: `mutation_rate=1` で「多数変化が発生」は仕様として弱い。
**Round 2 指摘**: `rate=1` で「attempted edits 数」と「effective diffs 数」のどちらを
保証するのか契約を固定すべし。

**本設計の契約（attempted-edits 契約）**:

- `mutation_rate` は **attempted mutation steps の期待回数 / K 比率** とする
- 各 attempt は対応する kernel を 1 回呼ぶが、**その結果がゲノムに構造差分を生む保証は無い**
  （例: weight_perturb で N(w, σ) から w 自身を引く確率は 0 に近いが理論上存在、
  params_perturb で同一値が引かれる可能性、enforce が lossy repair で元に戻す可能性）
- effective-diffs 保証は提供しない（lossy enforce / 確率的 noise との相互作用が複雑になるため）

**2 段階サンプリング**:

1. **attempt 回数決定**: `n_attempts ~ Binomial(K, mutation_rate)`（`K=3` default）
   - `mutation_rate=0` → `n_attempts=0` 確定（no-op 確定）
   - `mutation_rate=1` → `n_attempts=K` 確定（K 回 attempt 実施）
2. **kernel 種別割当**: 各 attempt について、**実行可能な** mutation kernel から一様選択
   - kernel を呼んでも構造が変わらないケース（effective-diff 0）はあり得る

| mutation kernel | 前提条件（選択候補入り条件） |
|-------------|---------|
| weight_perturb | 任意 directional / local_gate signal が存在 |
| params_perturb | `param_schema` 非空な signal が存在 |
| signal_add | 対象 clause に空きがある（max_depth 未満） |
| signal_del | directional は len > 1、gate は len > 0 |
| clause_add | `len(clauses) < max_clause` |
| clause_del | `len(clauses) > 1` |
| position_perturb | always |
| risk_perturb | always |

`position_perturb` / `risk_perturb` は always なので **候補集合は空にならない**。

**契約サマリ**:
- `mutation_rate=0` → `n_attempts=0` → 100% no-op（構造不変）
- `mutation_rate=1` → `n_attempts=K` → K 回 kernel 呼び出しが attempted（effective diff は保証しない）

### 2.4 random_gen 設計

- 初期世代は `max_clause=1` 固定（concept spec 通り）。後続 TODO で段階解放。
- `max_depth` は 1 clause 内の directional + local_gate の**幅の上限**（e.g. 4）
  - Round 1 指摘: これは「深さ」ではなく「幅」。名前変更候補 `max_width` も検討したが、
    呼び出し側との互換性のため `max_depth` を維持。ただし docstring に「幅 = signal 数上限」
    と明記
- PositionConfig / RiskConfig は妥当な範囲から一様サンプル（`enforce_consistency` が最終 clip）
- directional / local_gate の配置規約:
  - directional には category=`directional` な primitive のみ
  - local_gate には category=`modulator` な primitive のみ
  - ただし enforce はチェックせず、random_gen / operator が守る責任

### 2.5 Complexity penalty 設計（Round 1 指摘反映）

**Round 1 指摘**: `depth` は入れ子木の深さではなく「幅（clause 内 signal 数の最大値）」。
名前を明確化。

**新設計**:

```
n_clause    = len(clauses)
nodes       = sum(len(c.directional) + len(c.local_gate) for c in clauses)
max_width   = max(len(c.directional) + len(c.local_gate) for c in clauses)  # was "depth"
gate_nodes  = sum(len(c.local_gate) for c in clauses)

size_norm   = (nodes + 0.5 * max_width + 2 * (n_clause - 1) + 0.5 * gate_nodes) / size_ref
fitness_pen = fitness_raw - α * size_norm
```

- `size_ref` default: `10.0`（**暫定**。運用データに合わせて調整可）
- `α` default: `0.03`（**暫定**。T009 実 fitness 接続後に再評価）
- Luke & Panait 2006 の parsimony pressure は「サイズ罰則と制限の併用」を推奨
  → max_clause / max_depth の hard cap（enforce）+ α ペナルティ（runner）の二重化

### 2.6 Runner 設計（Round 1 指摘反映）

**Round 1 指摘**: evaluator 返り値 `float` 固定だと将来 raw fitness 以外のメタデータを渡せない。
`EvaluationResult` dataclass で拡張性を持たせる。

```python
@dataclass(frozen=True)
class EvaluationResult:
    """evaluator から runner への返り値。

    Attributes:
        fitness_raw: 未ペナルティの生 fitness。NaN/inf は runner 側で -inf に落とす。
        meta: 任意の追加情報（trades_count, sharpe, reason, regime, warnings 等）。
              型は Mapping[str, object] で string/int/float/bool/list など混在可。
    """
    fitness_raw: float
    meta: Mapping[str, object] = field(default_factory=dict)

Evaluator = Callable[[Genome], EvaluationResult]
```

- `run_ga(evaluator, config, registry)` の形で closure を受け取る設計
- `evaluator` の戻り値が NaN / inf の場合、runner 側で `-math.inf` に置換（個体は生存するが
  tournament では淘汰される）
- `GaConfig` に `complexity_alpha / complexity_size_ref / max_clause / max_depth` を追加

```python
@dataclass
class Individual:
    genome: Genome
    fitness_raw: float
    fitness_pen: float
    meta: Mapping[str, object] = field(default_factory=dict)
```

### 2.7 enforce_consistency の呼び出し規約（Round 1 指摘反映）

**Round 1 指摘**: enforce は lossy repair。operator の不整合が silently repaired されると
探索が実質 no-op 化しても見えにくい。責務を分離すべし。

**新設計**: 2 段構造。

- **operator 側の義務**: 構造不変条件を自ら守る
  - directional 空にしない（`signal_del` が最後の 1 本を消さない）
  - `len(clauses) >= 1`（`clause_del` が最後の 1 本を消さない）
  - `len(clauses) <= max_clause`（`clause_add` が超過しない）
  - weight / threshold / ATR は finite 値（非 finite を生成しない）
- **enforce_consistency の義務**: 最終正規化
  - weight / threshold の clip
  - entry / exit threshold の swap（entry > exit の強制）
  - 重複 name の dedupe
  - local_gate の最大 1 本化（> 1 の場合 |weight| max のみ残す）
  - clause > 3 の上位 3 本選抜（本 TODO では max_clause=1 なので発生しないが防御）

**異常系**:
- `enforce_consistency` が `ValueError` を raise した場合:
  - random_gen 内: bounded retry（最大 3 回）、超過でも raise するなら明示的 bug
  - crossover / mutate: 即 raise（operator の構造不変条件違反 = bug）
  - 呼び出し側で retry 再試行はしない（silent bug 潜伏防止）

## 3. インターフェース設計

### 3.1 `src/ga/_dummy_registry.py`（新設、private module）

```python
from src.ga.random_gen import PrimitiveSpec, PrimitiveRegistry

DUMMY_REGISTRY: Final[PrimitiveRegistry] = {
    # directional（docs primitives.md の name と完全一致させる）
    "TrendEMA": PrimitiveSpec("TrendEMA", "directional", "generic", {"n": (5, 50)}),
    "RSIRevert": PrimitiveSpec("RSIRevert", "directional", "generic", {"n": (5, 30), "level": (20.0, 80.0)}),
    "DonchianBreak": PrimitiveSpec("DonchianBreak", "directional", "generic", {"n": (10, 60)}),
    "ZScoreRevert": PrimitiveSpec("ZScoreRevert", "directional", "generic", {"n": (5, 40)}),
    # modulator（docs primitives.md の name と完全一致させる）
    "SessionGate": PrimitiveSpec("SessionGate", "modulator", "generic", {"start_h": (0, 23), "end_h": (0, 23)}),
    "ATRRegimeGate": PrimitiveSpec("ATRRegimeGate", "modulator", "generic", {"n": (10, 60), "k": (0.5, 2.0)}),
    "TrendStrengthGate": PrimitiveSpec("TrendStrengthGate", "modulator", "generic", {"n": (5, 30)}),
}
```

### 3.2 `src/ga/random_gen.py`

```python
@dataclass(frozen=True)
class PrimitiveSpec:
    id: str
    category: Literal["directional", "modulator"]
    domain: Literal["generic", "pair_specific"]
    param_schema: Mapping[str, tuple[float, float] | tuple[int, int]]

PrimitiveRegistry = Mapping[str, PrimitiveSpec]

def random_params(rng, spec: PrimitiveSpec) -> dict[str, float | int]: ...
def random_signal_config(rng, slot: Literal["directional", "local_gate"], registry: PrimitiveRegistry) -> SignalConfig: ...
def random_clause(rng, n_directional: int, n_gate: int, registry: PrimitiveRegistry) -> ClauseConfig: ...
def random_position_config(rng) -> PositionConfig: ...
def random_risk_config(rng) -> RiskConfig: ...
def random_genome(rng, name: str, units: int, *, max_clause: int, max_depth: int, registry: PrimitiveRegistry) -> Genome: ...
```

### 3.3 `src/ga/operators.py`

```python
def crossover(a: Genome, b: Genome, rng: random.Random) -> tuple[Genome, Genome]: ...
def mutate(
    genome: Genome,
    rng: random.Random,
    mutation_rate: float,
    *,
    max_clause: int,
    max_depth: int,
    registry: PrimitiveRegistry,
    n_edit_max: int = 3,
) -> Genome: ...
```

### 3.4 `src/ga/complexity.py`（新設）

```python
def genome_size_norm(genome: Genome, *, size_ref: float = 10.0) -> float: ...
def apply_penalty(fitness_raw: float, genome: Genome, *, alpha: float, size_ref: float = 10.0) -> float: ...
```

### 3.5 `src/ga/runner.py`

```python
@dataclass(frozen=True)
class EvaluationResult:
    fitness_raw: float
    meta: Mapping[str, object] = field(default_factory=dict)

Evaluator = Callable[[Genome], EvaluationResult]

@dataclass(frozen=True)
class GaConfig:
    population_size: int = 50
    generations: int = 20
    crossover_rate: float = 0.7
    mutation_rate: float = 0.3
    tournament_size: int = 3
    elite_count: int = 2
    max_clause: int = 1
    max_depth: int = 4
    units: int = 10000
    complexity_alpha: float = 0.03
    complexity_size_ref: float = 10.0
    n_edit_max: int = 3
    seed: int | None = None

@dataclass
class Individual:
    genome: Genome
    fitness_raw: float
    fitness_pen: float
    meta: Mapping[str, object] = field(default_factory=dict)

@dataclass
class GaResult:
    config: GaConfig
    best: Individual
    history: list[tuple[int, float]]
    final_population: list[Individual]

def run_ga(evaluator: Evaluator, config: GaConfig, *, registry: PrimitiveRegistry) -> GaResult: ...
```

## 4. テスト計画（Round 1 指摘反映）

### 4.1 `tests/ga/test_random_gen.py`（書き直し）

- `test_random_genome_passes_enforce`: 生成個体が `enforce_consistency` を例外なく通過
- `test_random_genome_max_clause_one`: `max_clause=1` で `len(clauses) == 1`
- `test_random_signal_uses_registry`: `SignalConfig.name` が registry に含まれる
- `test_random_signal_directional_only_directional`: directional slot では category=directional のみ
- `test_random_signal_gate_only_modulator`: local_gate slot では category=modulator のみ
- `test_random_params_in_schema_range`: 生成 params が schema 範囲内
- `test_random_genome_seed_deterministic`: 同 seed で同一ゲノム生成（再現性）
- `test_random_genome_params_no_alias`: 生成後に signal.params を mutate しても registry 側に影響なし

### 4.2 `tests/ga/test_operators.py`（書き直し）

- `test_crossover_passes_enforce`: 子 2 体とも enforce_consistency 通過（100 試行）
- `test_crossover_returns_two_children`: 戻り値が 2 要素 tuple
- `test_crossover_with_single_clause_parents`: 両親 max_clause=1 でも正常動作（実行可能 operator 集合が空にならない）
- `test_crossover_candidate_set_single_clause_single_directional`: 両親 max_clause=1 かつ
  各 clause の directional が 1 本のとき、candidate set は `{clause_swap, position_swap, risk_swap}` +
  （local_gate が片方でも非空なら `gate_swap`）。`clause_point` / `directional_swap` は候補に入らない
- `test_crossover_candidate_set_single_clause_multi_directional`: max_clause=1 だが directional が
  2 本以上 → `directional_swap` も候補入り
- `test_crossover_candidate_set_multi_clause`: max_clause=2 両親で clause_point も候補入り
- `test_crossover_parents_unchanged`: 親 Genome の identity が変わらない（純粋関数）
- `test_crossover_no_params_alias_to_children`: 子の signal.params を mutate しても親に影響なし
- `test_mutate_rate_zero_no_op`: `mutation_rate=0` → Genome 構造完全同一（1000 試行）
- `test_mutate_rate_one_attempts_k_times`: `mutation_rate=1, K=3` で attempt カウントが 3 回
  （kernel 呼び出し counter を spy で検証、effective diff ではなく attempts 数を確認）
- `test_mutate_passes_enforce`: rate=0.5 で 100 試行、全て enforce 通過
- `test_mutate_minimum_directional_preserved`: directional 最低 1 本維持（signal_del で全消失しない）
- `test_mutate_clauses_at_least_one`: clauses 最低 1 本維持
- `test_mutate_params_no_alias`: mutate 後の signal.params は別 object
- `test_mutate_seed_deterministic`: 同 seed / 同入力で同結果

### 4.3 `tests/ga/test_complexity.py`（新規）

- `test_size_norm_minimal`: 1 clause / 1 directional / 0 gate → 既知値 `(1 + 0.5*1 + 0 + 0) / 10 = 0.15`
- `test_size_norm_scales_with_signals`: signal 追加で size_norm 単調増
- `test_size_norm_clause_penalty`: n_clause=2 と n_clause=1 の差を確認
- `test_size_norm_gate_contribution`: gate 有無で差を確認
- `test_apply_penalty_alpha_zero`: α=0 で fitness 変化なし
- `test_apply_penalty_reduces_fitness`: α>0 で fitness 減少
- `test_apply_penalty_preserves_sign`: α でペナルティが raw を下回らないとは限らないが、式の線形性を確認

### 4.4 `tests/ga/test_runner.py`（書き直し）

- `test_run_ga_small_population`: `pop=5, gen=2, evaluator=lambda g: EvaluationResult(-size_norm(g))` で完走
- `test_best_in_final_population`: best individual が final_population に存在
- `test_history_length`: `len(history) == generations + 1`
- `test_elitism_preserves_best`: elite_count >= 1 で best fitness_pen 単調非減少
- `test_evaluator_nan_handled`: evaluator が NaN 返しても個体が存在、fitness_raw = -inf
- `test_evaluator_inf_handled`: 同様に +inf / -inf 扱い確認
- `test_run_ga_seed_reproducibility`: 同 seed / 同 evaluator で best / history 完全一致
- `test_run_ga_complexity_alpha_effect`: α=0 と α=0.1 で同 seed の挙動が変化することを確認

## 5. 学術引用（Round 1 指摘反映、役割分離）

- **Holland 1975** _Adaptation in Natural and Artificial Systems_ — building block 概念の起点
- **Goldberg 1989** _Genetic Algorithms in Search, Optimization, and Machine Learning_ — building block 用語
- **Koza 1992** _Genetic Programming_ — GP 全般の背景、tree crossover の基本
- **Montana 1995** _Strongly Typed Genetic Programming_ — 構造制約付き crossover（STGP）。
  実行可能 operator 集合選択の理論的背景
- **Poli 2008** _A Field Guide to Genetic Programming_ — parsimony pressure 一般論
- **Luke & Panait 2006** _A Comparison of Bloat Control Methods for Genetic Programming_ —
  size penalty + hard cap の併用推奨
- **Jacobs 1991 / Jordan 1994** _Mixture of Experts_ — Clause の意味論的背景（GA operator の根拠ではない）

## 6. リスクと軽減策

| リスク | 軽減策 |
|--------|--------|
| T010 未実装で実 primitive が無い | DUMMY_REGISTRY (`src/ga/_dummy_registry.py`) で代替、T010 で置換契約を明示 |
| crossover で実行可能 operator 集合が空 | 設計上空にならない（`position_swap` / `risk_swap` / `clause_swap` は always）、`AssertionError` で保険 |
| mutate で全 directional 消失 → enforce_consistency が ValueError | operator 側で directional 最低 1 本保証（signal_del 前提条件） |
| float fitness で NaN / inf が evaluator から返る | runner 側で `math.isfinite` チェック、非 finite は `-math.inf` |
| size_norm がスケールと合わずペナルティ効き過ぎ | α default=0.03、size_ref=10.0 で弱く、後続で SSOT 化 |
| enforce の lossy repair で silent no-op | operator 側が構造不変条件を守る責任分離、enforce は最終正規化のみ |

## 7. 実装順序

1. `src/ga/random_gen.py` 置き換え（PrimitiveSpec / random_* / docstring 整備）
2. `src/ga/_dummy_registry.py` 新設
3. `src/ga/complexity.py` 新設
4. `src/ga/operators.py` 置き換え（crossover / mutate）
5. `src/ga/runner.py` 更新（EvaluationResult / Individual / run_ga の evaluator 注入）
6. `tests/ga/test_random_gen.py` 書き直し
7. `tests/ga/test_complexity.py` 新規
8. `tests/ga/test_operators.py` 書き直し
9. `tests/ga/test_runner.py` 書き直し
10. pytest / mypy / ruff 全通し

## 8. 優先度・モード

- Priority: Critical
- Mode: standalone
- Theme: ga-architecture
