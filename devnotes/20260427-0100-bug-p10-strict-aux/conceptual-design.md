# 概念設計: P10 NADataProximityGate strict_aux 標準化

**起点監査**: [audit-codex.md §2 (18)](../20260427-0050-bug-hunt-audit/audit-codex.md) — confirmed P2

## 仮説

P10 NADataProximityGate は `event_snapshot=None` 時に 1.0 (gate 開放) を返す safe default を持つ。production loader 不在で常時このパスが発火し、**P10 を含む genome が GA selection で実質「常時 open gate × directional」として活用されている**。T039 で as_of_strict 枠は完成したが、データが無いままなので fail-fast にすべき。

## 検証済み事実

- [pair_specific.py:719-742](../../src/alpha_factory/primitives/pair_specific.py#L719-L742): `event_snapshot is None` で 1.0 + warning
- Run 20-22 観察: P10 を含む個体の Stage A pass 率 30-46% で機能しているように見えるが、実際は定数 1.0 信号
- T039 で snapshot.as_of_strict による per-bar gate は実装済だが、loader が無いと strict は発火しない

## 解決方針

production yaml で `strict_aux_required` を default true 化、aux データ未配線時に Stage A 評価を fail させる (現状 warning + safe default が問題)。テスト fixture では明示 false で従来通り動作。

選択肢:
- A. P10 だけ strict 化 (狭い影響)
- B. RegistryEvaluator.strict_aux_required を default true 化 (広い影響、T036/T039 整合)
- C. 別フラグ `event_snapshot_required` を新設 (Modulator gate 限定)

実装は B が最もシンプル。production GA で aux pipeline 未整備のままだと **すべての pair_specific が fail-fast で stage_a no_exposure / system_failure になる**ため、aux loader を整備する別 TODO (#bug-pair-specific-aux-loader) との連動が必須。

## 成功判定

- production runner で event_snapshot 不在時に primitive が safe default を返さず fail-fast
- 既存テストでは明示的に strict=False で safe default 経路保持
- aux loader 完成後 (別 TODO 完了後) に production toggle ON で正常動作

## 北極星制約

T039 の as_of_strict と並ぶ「観測精度 vs 計算可能性」の trade-off。fail-fast を default にすることで P2 観測歪み (定数信号化) を構造的に解消。
