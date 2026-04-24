## 判定: REVISE

## 全体所感
設計の方向性（pure logic と CLI 分離、deterministic 制御、skip 条件の明示）は妥当です。  
ただし、実装前に塞ぐべき設計不整合があり、このままでは挙動が不安定または解釈不一致になるため REVISE が妥当です。  
前提検証の観点では、コード未提示部分は **INCONCLUSIVE** として扱います（C8）。

## 観点別評価
1. 責務分離: 妥当です。`src` と `scripts` の分離で test 容易性は高いです。  
2. API 契約: dataclass は概ね十分ですが、`target_pass_rate` 範囲、`floor<=ceiling`、`aggregation_window>=1` などの設定値バリデーションが未定義です。  
3. aggregation 実装: **不整合あり**。`generation_weighted_mean` で pass rate は全世代、`fitness_pen_pool` は last_k と読める記述があり、「同一範囲 integrity 制約」と矛盾しています。  
4. controller 実装: clamp 順序は良いです。`p=1-target` の境界チェック、丸め後の再clamp方針が未定義です。  
5. yaml round-trip: ruamel 採用は適切です。単体キー更新の意図も明確です。  
6. atomic write: **競合リスクあり**。固定 `.tmp` 名は同時実行で衝突します。`os.replace` は atomic でも競合更新自体は防げません。  
7. schema check: **不足**。`stage_a_pass/generation/fitness_pen` の null をどう扱うかが未定義で、silent に集計歪みが出る余地があります。  
8. CLI exit code: 機械判定しやすい設計です。`--run-id` 指定ファイル不存在時の扱いを明文化するとより堅いです。  
9. test 計画: 量は十分ですが、null schema、競合書込み、`generation_weighted_mean` の整合性検証が抜けています。  
10. 転記漏れチェック: `calibrate.*` の YAML 追加は明記済みですが、**GaConfig ローダー反映経路**が設計本文で追跡できず INCONCLUSIVE。`genome.meta` への注入は不要なら「不要理由」を明文化すべきです。  
11. 依存追加: `ruamel.yaml` 追加自体は妥当。lockfile/既存テスト影響の検証手順を明記すべきです。  
12. smoke test: `n=12 < 30` で skip 確定は C7 的に正しいです。ただしそれ単体では controller 成功経路の動作確認にならず、成立は **部分的（INCONCLUSIVE）** です。

## 必須修正点（REVISE のみ）
- `generation_weighted_mean` の「pass_rate 集計範囲」と `fitness_pen_pool` 範囲を一致させ、式と文章を一本化する。  
- `stage_a_pass/generation/fitness_pen` の null/NaN 方針を明文化し、違反時は exit 8（schema mismatch）に統一する。  
- atomic write を固定 tmp 名から一意 tmp 名に変更する前提を設計に追記し、同時実行時の排他方針（lock か single-writer 前提）を明記する。  
- `calibrate.*` の転記経路を表で明示する（config定義 → GaConfig読込 → consumer参照、`genome.meta` は不要なら理由を記載）。  
- smoke を2段に分離する（skip 経路確認と、`n>=min_sample_size` の成功経路確認）。

## 推奨改善点（任意）
- `Decision` に「effective_sample_size」等の補助指標を追加し、C7の監査をしやすくする。  
- Monitoring 指標は因果解釈しない旨（C3）をログ項目説明に明記する。