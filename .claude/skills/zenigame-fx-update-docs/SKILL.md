---
name: zenigame-fx-update-docs
description: zenigame-fx Alpha Factory ドキュメントの陳腐化チェック・欠落検出・更新・用語定義整備を一括実行する
user-invocable: true
argument-hint: "[scope]  例: /zenigame-fx-update-docs 'clause 周り' or /zenigame-fx-update-docs（全体）"
---

# zenigame-fx Alpha Factory ドキュメント更新

`docs/alpha_factory/` 配下のドキュメントを、ソースコードの現状と突き合わせて陳腐化・欠落・用語未定義を検出し、更新する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `scope` ($1) | No | 更新対象のスコープ（省略時は docs/alpha_factory/ 全体） |

---

## 基本原則

### ハルシネーション防止

**ドキュメントに書く内容は必ずソースコードで裏取りすること。** 推測で書かない。

- 閾値・デフォルト値は `config/alpha_factory/default.yaml` またはソースから直接引用
- アーキテクチャ記述はソースのクラス・関数構造と一致
- 「〜と思われる」「〜の可能性がある」は禁止

### 用語定義の徹底

**初出の専門用語は必ず定義してから使う。**

- 各ドキュメントの冒頭に「本ドキュメントの主要用語」テーブル
- 他ドキュメントで定義済みの用語は `terminology.md` への参照
- 略語（IS/OOS, TC, IC, CRN, DSR, PBO 等）は初出で必ず展開

### パラメータ記載方針（ハイブリッド方式）

`config/alpha_factory/default.yaml` が全パラメータの SSOT。

**ドキュメントに値を残すもの**（アルゴリズム理解に不可欠）:
- 計算式・擬似コード中の閾値
- ソースコードにハードコードされた定数
- ゲート条件の閾値
- アルゴリズムの分岐条件に使われる値

**ドキュメントから削除し `default.yaml` 参照に置換するもの**:
- チューニング可能なデフォルト値テーブル
- フラグの on/off 状態（機能の存在のみ記述）

**置換時の記載形式**:
```markdown
## パラメータ

全パラメータのデフォルト値・変更根拠は `config/alpha_factory/default.yaml` の `{セクション}:` を参照。
```

### 最小変更の原則

- 正確な記述は変更しない
- 構造が変わっていない部分の書き直しは不要
- 新規ドキュメント作成は、既存に統合できない場合のみ

---

## Step 1: 現状把握

### 1-1. ドキュメント目次確認
```
Read docs/alpha_factory/README.md
```

### 1-2. ソースコード構造確認

`scope` に応じて `src/alpha_factory/`, `scripts/alpha_factory/`, `config/alpha_factory/` を探索。

### 1-3. 直近の変更ログ確認
```bash
git log --oneline -20
git log --oneline --follow docs/alpha_factory/
```

---

## Step 2: 陳腐化・欠落の検出

### 2-1. 対応関係マトリクス作成

| ドキュメントファイル | 対応するコード / 設定 | 最終変更日 | 乖離の可能性 |
|------------------|------------------|---------|------------|
| README.md | 全体 | - | - |
| clause-architecture.md | src/dsl/ | - | - |
| stage-gates.md | src/alpha_factory/stage_gate.py | - | - |
| primitives.md | src/alpha_factory/primitives/ | - | - |
| swim-lane.md | src/alpha_factory/swim_lane.py | - | - |
| statistics.md | src/alpha_factory/statistics.py | - | - |

### 2-2. 陳腐化チェック

各ドキュメントについて:
1. 記述されている関数・クラス・パラメータ名が現行コードに存在するか
2. 閾値・デフォルト値が `config/alpha_factory/default.yaml` と一致するか
3. 図・フローが現行実装と一致するか

### 2-3. 欠落チェック

新規追加されたコード・設定がドキュメント化されているか:
1. 新プリミティブが `docs/alpha_factory/primitives.md` に記載されているか
2. 新 Stage Gate 項目が `stage-gates.md` に記載されているか
3. config の新キーが対応ドキュメントに反映されているか

### 2-4. 用語未定義チェック

各ドキュメントの初出用語が `terminology.md` に定義されているか確認。未定義は追加。

---

## Step 3: 更新の実施

### 3-1. ドキュメント修正

検出した乖離・欠落・未定義用語を順次修正:
- Edit ツールで既存ドキュメント修正
- 必要に応じて新規セクション追加
- `terminology.md` に未定義用語追加

### 3-2. README.md 目次更新

新規ドキュメントを追加した場合、README.md の目次を更新。

### 3-3. AGENTS.md / CLAUDE.md の確認

- Alpha Factory 関連の運用手順が最新か
- 変更があったら Edit で更新

---

## Step 4: 完了報告

```
## ドキュメント更新完了

### 更新されたファイル
- docs/alpha_factory/primitives.md: {内容}
- docs/alpha_factory/terminology.md: {追加用語}
- ...

### 検出された問題
- 陳腐化: {N}件（修正済み: {M}件）
- 欠落: {N}件（追加済み: {M}件）
- 用語未定義: {N}件（定義追加済み: {M}件）

### 残課題
- {手動確認が必要な項目}
```

---

## 注意事項

- 推測で書かない（ソース裏取り必須）
- 日本語で記述
- コード例は実際に動作する形で（擬似コードは `# pseudo` と明記）
- 図は ASCII art でシンプルに（Mermaid 等は使わない）
