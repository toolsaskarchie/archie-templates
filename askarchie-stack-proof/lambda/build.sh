#!/usr/bin/env sh
# Packs the Lambda: handler + shared core + the seed quotes. No pip install needed.
#   dist/package/                           the unpacked package (a delivery that zips a folder points here)
#   dist/askarchie-stack-proof-lambda.zip   the same files, zipped
set -eu
cd "$(dirname "$0")"
rm -rf dist && mkdir -p dist/package
cp handler.py ../common/app.py ../common/archie_proof.py ../common/backends.py ../common/quotes.json dist/package/
(cd dist/package && zip -qr ../askarchie-stack-proof-lambda.zip .)
echo "dist/package/ and dist/askarchie-stack-proof-lambda.zip"
