## 本分析の前提
- Stage Gate / Archive / Cross-Pair の公開シグネチャは設計冒頭の既存仕様（T014〜T016）と一致していることを確認済み
- `LaneManager.__init__` は `tier1: dict[str, Tier1Lane]` を受け取り、dict のキーを通貨ペア（例: `"EUR_JPY"`）としつつ、各 `Tier1Lane.lane_id` は `"tier1_{instrument}"` 形式であることを強制している（§3.2.1）
- `LaneManager.run_generation(lane_id: str)` は引数で受け取った文字列をそのまま `_tier1` dict のキーに用いて Tier1Lane を検索する設計になっている（§3.2.4）

## Verdict: NEEDS_REVISION

## Facts
- `LaneManager.__init__` は `tier1` dict のキーを通貨ペア文字列として扱い、`lane.instrument == instrument` と `lane.lane_id == f"tier1_{instrument}"` の両方を同時に満たすよう検証している（§3.2.1）
- `LaneManager.run_generation` は `lane_id not in self._tier1` で存在確認を行い、ヒットすれば `lane = self._tier1[lane_id]` として Tier1Lane を取得する（§3.2.4）
- `LaneManager.get_all_lanes` は `Tier1Lane` インスタンス群（`lane.lane_id == "tier1_{instrument}"`）と `GraduationLane` を返す（§3.2.3）
- `GRADUATION_LANE_ID` は `"graduation"` で、`GraduationLane.lane_id` も `"graduation"` に固定されている（§2.1, §3.1）

## Interpretations
- `get_all_lanes` から取得した `Tier1Lane` の `lane_id` をそのまま `run_generation` に渡すと、`lane_id == "tier1_{instrument}"` が `_tier1` のキー（`instrument`）と一致せず、`KeyError("unknown lane_id")` になるため、公開 API の基本的な利用フローが破綻する
- 既存の GA オーケストレータ（T014 前提）は lane_id 文字列を識別子として扱う設計であり、`run_generation` が lane_id と通貨ペアキーを混同している現状では interface 整合性が満たせない

## 修正点
1. §3.2.1 / §3.2.4 (`LaneManager.__init__` と `run_generation`)  
   - `_tier1` を lane_id キーで再インデックスする、または `run_generation` 内で `lane_id` から通貨ペアキーを復元する（例: `lane_id.removeprefix("tier1_")`）。合わせて `_validate_intraday_constraint` のサンプル呼び出しも新しいキー構造に適合させる。  
   - これにより lane_id ベースの公開 API と `Tier1Lane.lane_id` の契約が整合する。