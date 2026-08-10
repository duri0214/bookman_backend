Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path "manage.py")) {
  throw "manage.py が見つかりません。リポジトリのルートで実行してください。"
}

python manage.py flush --noinput
python manage.py loaddata `
  bookman/fixtures/municipality-data.json `
  bookman/fixtures/branch-data.json `
  bookman/fixtures/category-data.json `
  bookman/fixtures/author-data.json `
  bookman/fixtures/book-data.json `
  bookman/fixtures/branch-book-stock-data.json `
  bookman/fixtures/customer-data.json `
  bookman/fixtures/library-staff-data.json `
  bookman/fixtures/branch-closed-day-data.json `
  bookman/fixtures/lending-data.json `
  bookman/fixtures/reservation-data.json `
  bookman/fixtures/search-condition-data.json
