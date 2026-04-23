前提検証（C4）を先に明示します。

- `Fact`: このスレッドには設計本文が未展開で、参照はファイルパス指定のみです。  
- `Fact`: ご指定どおり「コマンド実行なし」を厳守すると、こちらからローカルファイル内容を取得できません。  
- `Interpretation`: lookahead/O(N)/PrimitiveSpec契約/NaN伝播/F6境界/F13 warmup/F14次元/registry冪等性を**事実ベースで厳密判定**するための根拠が不足しています。

判定: **INCONCLUSIVE（= NEEDS_REVISION）**

Must-fix（レビュー実行条件として最重要3件）  
1. [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-0812-primitives-directional-generic/detailed-design.md) の該当章（14 primitive擬似コード、F6/F13/F14、registry統合）本文共有  
2. [_base.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_base.py) の `PrimitiveSpec` と `_REQUIRED_DATA_LITERALS` 定義共有  
3. [_registry.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_registry.py) / [__init__.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/__init__.py) の登録フロー共有

上記テキストを貼っていただければ、指定フォーマット（Must-fix / Should-consider / Nit、最後に APPROVED/NEEDS_REVISION）で即時レビューします。