#!/usr/bin/env sh
# Packs the Lambda zip: handler + shared core + the seed quotes. No pip install needed.
set -eu
cd "$(dirname "$0")"
rm -rf dist build && mkdir -p dist build
cp handler.py ../common/app.py ../common/archie_proof.py ../common/backends.py ../common/quotes.json build/
(cd build && zip -qr ../dist/askarchie-stack-proof-lambda.zip .)
rm -rf build
echo "dist/askarchie-stack-proof-lambda.zip"
