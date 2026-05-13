# PR6: F6 grammar soft downweight 詳細設計

## 実装方針

### config

```python
@dataclass(frozen=True)
class GAConfig:
    ...
    primitive_weights: Mapping[str, float] = field(default_factory=dict)
    # default 空 dict = 全 primitive 重み 1.0 (= 完全行動不変)
```

yaml:
```yaml
ga:
  primitive_weights:
    F6: 0.5
    F10: 0.5
    F4: 0.5
    F7: 0.5
```

### genome generation / mutation での反映

`src/ga/grammar.py` (or 等価 module) の primitive sampling で `random.choices(weights=...)` を使う。

### CLI

PR4/PR5 と同型で `--primitive-weight F6=0.5 --primitive-weight F10=0.5` 等 (= 複数指定可)。

## 受入基準

- [ ] GAConfig.primitive_weights 追加
- [ ] genome sampling で重み反映
- [ ] default 全 1.0 = 行動完全不変 (= 既存 test 全 pass)
- [ ] PR6 tests (= weights 反映の unit test、 sampling 統計 test)
- [ ] CLI 引数追加

## トリガー条件 (= conditional → open 昇格条件)

PR4 smoke の結果 (= ユーザー実行待ち) で:
- top decile (= fitness_pen 上位 10%) における F6 含有率が baseline × 1.5 超

確認時に本 TODO を Open に昇格、 plan-and-design で実装着手。

## smoke 合格条件

- 既存 GA 動作不変 (= default 全 1.0)
- weights 適用時に F6 出現率が yaml 比率に比例

## コミット計画

- 1 コミット: `feat(ga): primitive_weights grammar soft downweight (PR6、 default 全 1.0)`
