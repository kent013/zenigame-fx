# Round 1 Detailed Design Review

## 施策 1 (rolling_max Numba) 判定
**APPROVE**

- [Fact] 設計の circular buffer 更新式は、現行 `deque` 実装の drop 条件 (`<=`) と window 条件 (`dq[0] <= i-n`) を保っています（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/detailed-design.md:103), 現行は [_indicators.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py:126)）。
- [Fact] `n=1` の `(tail-1+n)%n` は常に `0` になり、off-by-one は発生しません。
- [Suggestion] parity test に `n=1` と「同値が連続する系列」を明示追加すると comparator 契約がより固くなります。

## 施策 2 (rolling_min Numba) 判定
**APPROVE**

- [Fact] 施策1と対称で、比較子のみ `>=` に変更されており、現行契約と整合します（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/detailed-design.md:183), 現行は [_indicators.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py:148)）。
- [Suggestion] 施策1と同様、`n=1` と重複値ケースを parity に入れると十分性が上がります。

## 施策 3 (_wilder_smooth Numba) 判定
**REQUEST_CHANGES**

- [Critical] 「non-NaN を `assert_array_equal` で完全一致」という目標に対し、手動 seed 集計 (`s/cnt`) は現行 `np.nanmean` 系 seed と丸め順序が一致せず、微小差が出ます（例: `4.26e-14`）。  
  これは反証可能で、乱択入力で再現済みです。
- [Interpretation] 取引上の影響はほぼ無視できる差ですが、「exact parity」を要件に据えるなら blocker です。
- [最小変更案] seed 計算だけは現行どおり Python 側で `np.nanmean/mean` を使い、`i>=n` の recurrence 部分だけ JIT 化してください。これで exact parity 要件と高速化を両立できます。

## テスト計画 (parity test) 評価

- [Fact] a-e ケース（全finite/先頭NaN/途中NaN/全NaN/length<n）は妥当です（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/detailed-design.md:307)）。
- [Warning] exact parity を維持するなら、施策3は上記最小変更が先に必要です。
- [Fact] `adx()` 経由 parity test は必要です。`_wilder_smooth` が `atr/adx` の両方に波及するためです（[_indicators.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py:456), [_indicators.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py:471)）。
- [Suggestion] oracle は git history 参照ではなく、テスト内に固定実装を持つ方が再現性が高いです。
- [Warning] 既存 pytest 走破は sandbox 制約で実行確認できませんでした（`uv` キャッシュ領域/一時ディレクトリ不可）。

## 全体判定
**CHANGES_REQUESTED**

- 収束条件に沿って 1 点に絞ると、反証可能仮説は「`_wilder_smooth` manual seed では exact parity が崩れる」。
- 最小変更は「seed を現行 numpy 実装のまま維持し、tail recurrence のみ JIT 化」。

## 主要指摘 / 推奨事項

1. **Q1 (`n=1` edge)**: 正しいです。`(tail-1+n)%n` は常に有効 index を返し、off-by-one はありません。  
2. **Q2 (int→float cast)**: `float(n-1), float(n)` 自体は問題ありません。差分の主因は cast ではなく seed 集計アルゴリズム差です。  
3. **Q3 (`cache=True` と cache 削除)**: 削除時は correctness ではなく cold compile 時間だけ悪化します。CI は基本 cold 前提で見積もるのが安全です。  
4. **Q4 (oracle 実装)**: git history 依存は不可。テスト内に self-contained oracle を置く方針が妥当です。  
5. **Q5 (残 blocker)**: 施策3の exact parity 仕様のみが残 blocker。施策1/2はこのまま進めて問題ありません。  

C1/C4確認: 概念設計 Round2 APPROVED は参照済み（[conceptual-review-round-2.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/conceptual-review-round-2.md:2)）。profile hot path と line 番号、既存 Numba 使用例も確認済み（[profile_20260505_171107.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_171107.txt:86), [profile_20260505_171107.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_171107.txt:98), [composite.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py:144)）。