**全体判定: APPROVED**

Fact: Round 1 の Critical 2 件は、設計上は解消されています。  
Interpretation: 残存は実装時に潰すべき Warning/Suggestion であり、詳細設計としては実装へ進めてよい水準です。

**施策別判定**

| 施策 | 判定 |
|---|---|
| 1. `EquityCurve` 型 + encode/decode | APPROVE |
| 2. `run_backtest` producer 変更 | APPROVE |
| 3. `compute_metrics` 対応 | APPROVE |
| 4. consumer 全追従 | APPROVE |
| 5. shadow test + 効果検証 | APPROVE |

**残存指摘**

[Warning] `__post_init__` の `setflags(write=False)` は配列オブジェクト自体を read-only にしますが、外部から渡された view の base 配列経由の書換までは完全には防げません。  
修正案: `EquityCurve` コンストラクタ内で `np.array(arr, dtype=np.int64, order="C", copy=True)` に正規化し、`object.__setattr__` で差し替えてから `setflags(write=False)` する。性能が気になる builder 経路だけは owned array を渡す private constructor に分けてもよいです。

[Warning] `np.diff(self.epoch_ns) > 0` は int64 極値付近で差分 overflow の余地があります。  
修正案: strict 昇順検証は `np.all(self.epoch_ns[1:] > self.epoch_ns[:-1])` にする。

[Warning] archive Parquet の byte-level 比較は、Parquet writer metadata や row group 差分で偽陽性になる可能性があります。  
修正案: raw Parquet file bytes ではなく、同一ソート後の canonical row stream、または既存 serializer の正規化出力を byte-level 比較対象にする。

[Suggestion] `EquityCurveBuilder.append()` は overfill も明示的に検出した方がよいです。  
修正案: `self._i >= len(self._epoch)` なら `EquityCurveError` を raise し、`test_builder_detects_overfill` を追加する。

[Suggestion] `ensemble.py` は checked add に加えて、各 run の `epoch_ns[:length]` が一致することを検証すると安全です。  
修正案: 既存挙動は index 合算ですが、timestamp 不一致は意味論上危険なので fail-closed に寄せる価値があります。

**重点再判定**

Fact: `__post_init__` に dtype / C-contiguous / strict 昇順 / `setflags(write=False)` が入ったことで、Round 1 の read-only Critical は主要経路では解消されています。  
Interpretation: alias 経由の完全防御まで求めるなら copy 正規化を実装時に追加してください。

Fact: consumer 機械抽出証跡は commit `8d2c86a`、対象 line、`paper_trading` 非参照まで含んでいます。  
Interpretation: 詳細設計の証跡として十分です。実装時に `src/ tests/ scripts/` を再 grep して差分ゼロを確認すれば禁止事項 8 のリスクは管理できます。

Fact: ensemble の Python `int` 合算、範囲検証、`np.int64` 配列化の方針は silent overflow を避けます。  
Interpretation: 正しい方向です。timestamp alignment 検証だけ追加するとさらに堅いです。

Fact: `decode_epoch_ns` の sub-microsecond reject と `validate_equity_scale_contract(config)` の起動時 fail-closed は、lossless 契約と SCALE 前提を明示化しています。  
Interpretation: holding cost 有効化時に静かに壊さない判断であり、本 T105 の範囲では妥当です。

**先人の知恵**

- Paul R. Wilson, Mark S. Johnstone, Michael Neely, David Boles, 1995, *Dynamic Storage Allocation: A Survey and Critical Review*
- David Goldberg, 1991, *What Every Computer Scientist Should Know About Floating-Point Arithmetic*
- Charles R. Harris et al., 2020, *Array programming with NumPy*

この設計は「金額計算は Decimal のまま」「保存表現だけ scaled-int にする」という境界が明確です。live_criteria、fitness、約定・margin・手数料の因果ループを切らずに、retained object churn の発生源を狙っているため、T105 として APPROVED です。