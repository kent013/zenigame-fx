# PR6: F6 grammar soft downweight opt-in (= conditional、 PR4 smoke で F6 増幅確認時のみ実施)

## 背景

archive 実測で F6 primitive が Stage A only 集団で過剰増幅される傾向 (= sharpe 偏重 fitness の副作用)。 ただし Stage C 20k+ 集団に F6 がほぼ出ない (= Stage C 持続性 0%)。 Codex H_Z' (= F6/F10/F4/F7 が dead primitives) は archive 単独では確定不能。

## トリガー条件

PR4 smoke で **F6 含有率が top decile で baseline × 1.5 超** 確認時に着手 (= conditional)。 PR4 smoke 結果が出るまで本 TODO は Conditional table に保留。

## 目的

PR4 smoke で F6 増幅確認時、 F6/F10/F4/F7 を grammar 探索 prior で soft downweight (= fitness penalty ではなく primitive sampling 確率を低下):

```yaml
ga:
  primitive_weights:
    F6: 0.5  # default 1.0、 0.25-0.5 で soft downweight
    F10: 0.5
    F4: 0.5
    F7: 0.5
```

= fitness penalty (= 目的関数に primitive 名混入) は Codex Y Round 4 で REJECTED、 grammar prior が責務明確。

## 期待効果

- F6 系 primitive の探索集中緩和
- 他 primitive (= F8/F5/M2/P1/P7 等の Stage C 通過可能性ある) の探索拡大

## スコープ

- `GAConfig` に `primitive_weights: dict[str, float]` 追加
- genome generation / mutation で primitive sampling に重み反映
- default 全 1.0 (= 行動完全不変)
- 1 RUN smoke 必須 (= 行動変更)

## 非目的

- F6 hard ban (= Codex Y Round 4 で禁止)
- fitness penalty (= 同上)

## 参考

- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 12 段 TODO 順 8
- `tmp/codex-debate-round2/.codex-output-debate-Y-round-4.md` § Q3
