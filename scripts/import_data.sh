#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f "manage.py" ]]; then
  echo "manage.py が見つかりません。リポジトリのルートで実行してください。" >&2
  exit 1
fi

python manage.py loaddata \
  bookman/fixtures/municipality-data.json \
  bookman/fixtures/branch-data.json \
  bookman/fixtures/category-data.json \
  bookman/fixtures/author-data.json \
  bookman/fixtures/book-data.json \
  bookman/fixtures/branch-book-stock-data.json \
  bookman/fixtures/customer-data.json \
  bookman/fixtures/library-staff-data.json \
  bookman/fixtures/branch-closed-day-data.json \
  bookman/fixtures/lending-data.json \
  bookman/fixtures/reservation-data.json \
  bookman/fixtures/search-condition-data.json
