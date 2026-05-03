制約に従い、コマンド実行とファイル書き込みは実施していません。以下をレビュー本文としてそのまま使用できます。

## 前提検証（C4）
- Verified: ユーザー提示の対象ファイル名、仮説文、評価観点、テスト計画要約（smoke 5ケース×2 stage）。
- Unverified: 実コード断片、`detailed-design.md` 本文、`stage_gate.py` 実差分、既存テスト実装内容、実測メモリ、parquet集計。
- 判定上の扱い: 実証不足項目は **INCONCLUSIVE** を優先（C8）。

## 施策別レビュー（Round 1: Falsification-first）

### 施策1: helper完全再利用（Stage B 18m / Stage C 60d）
- 判定: **REQUEST_CHANGES**
- Fact: 仮説は「Stage Aで確立した helper を Stage B/C に完全再利用」。
- Interpretation: 時間軸・評価窓・コスト反映・欠損パターンが異なるため、入力契約不一致で「完全不変」が崩れる反証余地が大きい。
- [Critical] 入力契約の明文化不足により、`NaN`/`Inf`/空系列時の振る舞いがStage間で暗黙分岐化するリスク。  
  修正案: helperの pre/post 条件を型・docstring・assert で固定し、Stage B/C側で正規化アダプタを必須化。
- [Warning] イントラデイ制約（オーバーナイト禁止）とコスト（スプレッド/スワップ）適用タイミングがStage依存でズレる可能性。  
  修正案: 「バー時点コスト控除契約」を1箇所に集約し、A/B/C共通テストで同一検証。
- [Suggestion] helper I/Oを Protocol 化し、署名変更時の波及を静的検知。

### 施策2: 例外隔離（log try/except + helper内部try）
- 判定: **REQUEST_CHANGES**
- Fact: 例外を隔離して主判定経路の不変性を守る設計意図。
- Interpretation: 広域 `except` は障害の不可視化を招き、回帰0を偽陽性化しうる。
- [Critical] 例外握りつぶしで「判定は通るがログ欠落・診断不能」になる運用リスク。  
  修正案: 捕捉例外を限定し、`error_code`/`stage`/`genome_id` を構造化ログへ強制出力。失敗件数が閾値超過時は run fail-fast。
- [Warning] Stage Aと「完全同型」を主張するには、例外種別・復帰条件・ログキー一致の証跡が必要。  
  修正案: A/B/Cで例外注入テスト（同一入力）を実施し、出力同型性を比較。
- [Suggestion] ログ失敗時のサーキットブレーカを追加。

### 施策3: regression 0 のrigor（判定回帰0 + 運用回帰 + Stage A不変）
- 判定: **REQUEST_CHANGES**
- Fact: 回帰ゼロを要求。
- Interpretation: smoke中心では「非劣化証明」として不足。
- [Critical] ゴールデン比較対象の不足（複数market regime、欠損含む）で回帰0主張は弱い。  
  修正案: 固定seed・固定データで A/B/C 判定結果の完全一致テストを追加（成功/失敗/境界を最低3群）。
- [Warning] 運用回帰（ログ量、失敗率、実行時間、メモリ）未計測だと本番劣化を見逃す。  
  修正案: CIでメトリクス閾値を設定し、逸脱時に失敗。
- [Suggestion] 「不変対象」と「変更許容対象」を設計書に分離記載。

### 施策4: commit A（rename）と commit B（behavior wiring）分離純度
- 判定: **INCONCLUSIVE**
- Fact: 2コミット分離方針は妥当。
- Interpretation: diff実物未確認のため純粋性は断定不可。
- [Warning] renameのみでも import path / 反射 / シリアライズキーが変わると挙動変化が起きる。  
  修正案: commit A単独で全テスト通過＋公開APIシグネチャ差分ゼロを自動検証。
- [Suggestion] commit A に「機械的renameのみ」ルール（ASTベース検査）を追加。

### 施策5: テスト計画（5ケース×2 stage）
- 判定: **REQUEST_CHANGES**
- Fact: 提示計画は10ケース。
- Interpretation: NaN伝播・並列競合・境界時間を網羅するには不足。
- [Critical] 欠損値/空系列/単一約定/コスト極値/時間境界（営業日跨ぎ）未網羅だとロジック欠陥を取りこぼす。  
  修正案: 最低でも「契約テスト」「異常系」「並列ログ競合」「メモリ上限」「回帰ゴールデン」を追加。
- [Warning] Stage A不変確認が独立ケース化されていない可能性。  
  修正案: Stage A専用の非回帰スイートを固定化。
- [Suggestion] テスト命名を振る舞いベースに統一し、セッション固有名を排除。

### 施策6: メモリ概算（+50MB/worker）
- 判定: **INCONCLUSIVE**
- Fact: 実行環境は24GB、6 worker、1 worker目安3GB。
- Interpretation: dual-pathで配列複製が起きると +50MB は楽観的な可能性。
- [Warning] ピークRSSはデータ長・並列度・一時配列で非線形に増える。  
  修正案: 実測（RSS/alloc）を Stage別・データ長別に取得し、worst-caseで3GB未満を確認。
- [Suggestion] SoA・prefix-sum再利用・中間配列再利用で上限を設計時点で固定。

### 施策7: 未捕捉 cross-cutting concern
- 判定: **REQUEST_CHANGES**
- Fact: helper再利用は呼び出し点増加を伴う。
- Interpretation: 波及変更漏れが最も起きやすい。
- [Critical] archive/schema 伝搬漏れ（禁止事項8）を誘発するリスク。  
  修正案: schema version固定、reader後方互換テスト、書き込み経路の一括検証を追加。
- [Warning] worker並列時のログ競合・順序非決定で診断困難化。  
  修正案: `run_id + worker_id + genome_id` を必須キー化し、行単位で一意化。
- [Suggestion] helper署名変更を検知する影響範囲チェックリストをPRテンプレ化。

## C3/C7（Collider bias / Sample size）
- Fact: 本stepは主に配線と評価経路再利用で、相関・予測力の新規claimは主題外。
- Interpretation: それでも「改善した」主張を行う場合は n を明示し、n<30で因果解釈を避けるべき。
- [Suggestion] 成果報告テンプレに `n`, conditioning set, 反証結果を必須項目として追加。

## 全体判定
- **CHANGES_REQUESTED**
- 理由: 仮説の中核（「完全再利用で既存判定完全不変」）に対し、入力契約・例外隔離・回帰証明・cross-cutting検証の証拠が不足。特にテスト計画は現状の10ケースでは不十分。

## 保存について
- 指定先 [`detailed-review-round-1.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-review-round-1.md) への書き出しは、あなたの「コマンド実行・ファイル書き込み禁止」制約に従い未実施です。