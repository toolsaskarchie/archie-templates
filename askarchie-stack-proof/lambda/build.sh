#!/usr/bin/env sh
# Packs the Lambda: handler + shared core + the seed quotes. No pip install needed.
#   dist/package/                           the unpacked package (a delivery that zips a folder points here)
#   dist/askarchie-stack-proof-lambda.zip   the same files, zipped
set -eu
cd "$(dirname "$0")"
rm -rf dist && mkdir -p dist/package
cp handler.py ../common/app.py ../common/archie_proof.py ../common/backends.py ../common/quotes.json dist/package/
# The zip is a convenience for a manual upload; a builder without `zip` still has the folder.
if command -v zip >/dev/null 2>&1; then
  (cd dist/package && zip -qr ../askarchie-stack-proof-lambda.zip .)
  echo "dist/package/ and dist/askarchie-stack-proof-lambda.zip"
else
  echo "dist/package/ (no zip binary here; the folder is the package)"
fi
