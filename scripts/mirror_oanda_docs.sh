#!/usr/bin/env bash
# OANDA 公式ドキュメントのローカルミラー。
# docs/oanda/jp-v1/ と docs/oanda/v20/ に保存する。
# 再取得用。成果物は .gitignore 済み。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/oanda"
cd "$OUT"

WGET="${WGET:-/opt/homebrew/bin/wget}"
if [ ! -x "$WGET" ]; then
  WGET="$(command -v wget || true)"
fi
if [ -z "$WGET" ]; then
  echo "wget not found. install via: brew install wget" >&2
  exit 1
fi

UA='Mozilla/5.0 (zenigame-fx docs mirror)'

mirror() {
  "$WGET" --mirror --convert-links --adjust-extension --page-requisites --no-parent \
    --wait=1 --random-wait -e robots=off -U "$UA" \
    "$1"
}

# 日本語 v1 docs
mirror "https://developer.oanda.com/docs/jp/"

# 英語 v20 docs（各セクションを個別に取得。一部 404 あり＝正常）
for p in introduction best-practices development-guide \
         account-ep instrument-ep order-ep trade-ep position-ep transaction-ep pricing-ep \
         primitives-df account-df instrument-df order-df trade-df position-df transaction-df pricing-df; do
  mirror "https://developer.oanda.com/rest-live-v20/$p/" || true
done

# 並び替え
rm -rf jp-v1 v20 shared
mv developer.oanda.com/docs/jp jp-v1
mv developer.oanda.com/rest-live-v20 v20
mkdir -p shared
mv developer.oanda.com/docs/shared/* shared/ 2>/dev/null || true
mv developer.oanda.com/docs/css shared/css-top 2>/dev/null || true
mv developer.oanda.com/docs/bootstrap shared/bootstrap 2>/dev/null || true
rm -rf developer.oanda.com

echo "mirror updated: $(du -sh "$OUT" | cut -f1)"
