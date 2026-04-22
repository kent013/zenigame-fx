# Swim Lane

## 目的

スイムレーン（Tier 1 + Graduation lane）の構造と graduation 条件を一箇所に集約する。実装詳細は `concepts/swim-lane-manager.md` および後続 TODO で扱う。

## スコープ

- Tier 1 = per-instrument GA の構造
- Graduation lane = 卒業個体集合での universal 探索
- Graduate 条件
- レーン間の個体フロー

数値（population_size、target ペアリスト）は SSOT 参照。

## 用語リンク

本ドキュメントで使用する用語: [Tier](terminology.md#tier), [Lane](terminology.md#lane), [Graduation](terminology.md#graduation), [Stage C](terminology.md#stage-c), [(ii-lite)](terminology.md#ii-lite), [Anchor Pair](terminology.md#anchor-pair)

## 主要定義

### Tier 1 — per-instrument GA

- 1 instrument につき 1 lane
- 各 lane が独立して population を保持し、generation を進める
- target instrument は `improve_cycle.target_priority` の順序で巡回
- archive には `instrument` カラムが必須（cross-pair 分析の前提）

### Graduation Lane — universal 探索

- Tier 1 から graduate した個体だけを集めた universal lane
- 全 instrument 横断で評価、ロバスト性検証

### Graduate 条件

```
Graduate = (Stage C 通過) AND ((ii-lite) shadow 基準超え)
```

両条件を AND で満たした個体のみ Graduation lane に昇格する。

### レーン間フロー

```
[Tier 1: EUR_USD] ─┐
[Tier 1: USD_JPY] ─┤
[Tier 1: EUR_JPY] ─┼─(graduate)──> [Graduation Lane (universal)]
[Tier 1: AUD_JPY] ─┤
[Tier 1: USD_CAD] ─┤
[Tier 1: USD_ZAR] ─┘
```

Tier 1 → Graduation の一方向（後退無し）。Graduation lane で再評価されない場合の rollback ポリシーは別 TODO。

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| target instrument | `dataset.instrument`（現行は単一。Phase 2I で `dataset.instruments` 配列化予定） |
| population_size_tier1 | Phase 2I で `ga.population_size_tier1` 追加予定（未定義） |
| population_size_graduation | Phase 2I で `ga.population_size_graduation` 追加予定（未定義） |
| improve_cycle.target_priority | Phase 2I で追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — Graduate 条件の片方
- [cross-pair.md](cross-pair.md) — Graduate 条件のもう片方
- [clause-architecture.md](clause-architecture.md) — 各 lane で扱うゲノム構造
- [concepts/swim-lane-manager.md](concepts/swim-lane-manager.md)

## 関連 TODO

- 未着手（Phase 2G: `src/alpha_factory/swim_lane.py`）
