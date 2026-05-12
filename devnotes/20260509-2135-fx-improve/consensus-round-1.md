## Q1 推薦案 (B)
仮説: elite collapse 悪化が seed 依存の偶然か構造的退化か切り分けできておらず、再現性検証が先行しないと以降の施策評価が曖昧になる。最小変更で Run 57 と同一条件を再走することで、fp 分布・trade_count の分散を定量化し、次サイクル以降の設計判断に必要なデータを確保できる。

## Q2 案A のリスク評価
- run_ga.py の評価ループへ 50 行規模の追加が入り、Stage A/B/C の境界扱いを誤ると live_criteria 違反や Stage partition guard 破綻を招く。
- SessionBlock 再構築ロジックにバグがあると DSR が偽値になり、スワップ/スプレッド込み fitness の信頼性をさらに毀損する。
- regression テスト不備のまま導入すると、20 RUN 完走に必要な安定スループット (run/日) が一時停止し、cycle 5 のタイムラインに影響。

## Q3 cycle 5-6 組み合わせ推薦 (Y)
cycle 5 で seed 43 の再現性チェック (案B) を行い、elite collapse の再発性を検証。得られた観測を前提に cycle 6 で DSR 配線復帰 (案A) を実装すれば、run_ga.py 変更時のテスト設計を seed 差分データで補強でき、20 RUN を止めずに進行できる。

## Q4 Codex 推薦施策
cycle 5 は案B「再現性チェック」を採用。seed 変更のみで Stage partition guard・trade_count 条件を保ったまま variance プロファイルを取得し、DSR 復旧のテストベッドを整える。並行して DSR 再配線に必要な SessionBlock 設計・テストパターンを devnotes 側で先行準備する。

## 全体判定: APPROVED (B)