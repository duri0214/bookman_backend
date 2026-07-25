# Bookman Backend

Bookman のバックエンドです。

Django / Django REST Framework で API を提供し、同じ親フォルダにある `bookman_nextjs` の Next.js フロントエンドと連携します。

```text
dev/
  portfolio/
  bookman_backend/
  bookman_nextjs/
```

## Codex 運用

このリポジトリは、同じ親フォルダにある `portfolio/.codex` を Codex 運用ルールとスキルの管理元として参照します。

詳細は `AGENTS.md` を参照してください。

## 初回セットアップ

バックエンドのコマンドは Python 3.12 以上を前提にします。

```console
python --version
python -m pip --version
```

Python 3.12 以上であることを確認してから、仮想環境を作成します。

```console
python -m venv venv
```

仮想環境を有効化し、pip を更新します。

```console
.\venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
```

依存関係をインストールします。

```console
python -m pip install -r requirements.txt
```

## 環境変数

Django の設定は `.env` から読み込みます。

```env
DJANGO_DEBUG_MODE=True
DJANGO_SECRET_KEY=django-insecure-...
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_USER=python
DJANGO_DB_PASSWORD=...
DJANGO_DB_NAME=bookman_db
DJANGO_DB_PORT=3306
```

`.env` は Git 管理しません。`.env.example` をコピーして、DB 名、ユーザー名、パスワードはローカル MySQL の設定に合わせます。

## データベース

migration を適用します。

```console
python manage.py migrate
```

モデルを変更した場合だけ、migration を作成します。

```console
python manage.py makemigrations bookman
```

migration の未生成差分を確認します。

```console
python manage.py makemigrations --check --dry-run
```

開発用 DB のデータを入れ直す場合は、Django 管理下のテーブルを空にしてから初期データを読み込みます。

```console
python manage.py flush --noinput
```

`flush` は既存データを削除します。開発用 DB だけで実行し、本番 DB や共有 DB では実行しないでください。
MySQL では通常、主キーの自動採番もリセットされます。テーブル定義や migration 状態から作り直したい場合は、DB を作り直してから `python manage.py migrate` を実行してください。

初期データを読み込みます。

```console
python manage.py loaddata bookman/fixtures/municipality-data.json
python manage.py loaddata bookman/fixtures/branch-data.json
python manage.py loaddata bookman/fixtures/category-data.json
python manage.py loaddata bookman/fixtures/author-data.json
python manage.py loaddata bookman/fixtures/book-data.json
python manage.py loaddata bookman/fixtures/branch-book-stock-data.json
python manage.py loaddata bookman/fixtures/customer-data.json
python manage.py loaddata bookman/fixtures/library-staff-data.json
python manage.py loaddata bookman/fixtures/branch-closed-day-data.json
python manage.py loaddata bookman/fixtures/lending-data.json
python manage.py loaddata bookman/fixtures/reservation-data.json
python manage.py loaddata bookman/fixtures/search-condition-data.json
```

第二期の画面確認用 fixture では、以下の状態をまとめて確認できます。

- すべての本に支店別所蔵があり、同じ本が複数支店にある状態
- 支店間移動で、移動先に既存行があるケースとないケース
- 貸出上限が異なる利用者、貸出中/返却済みの貸出データ
- 予約待ち、取り置き中、期限注意、期限切れ、取消済みの予約データ
- 複数支店の `counter` / `manager` / `admin` 職員と保存済み検索条件

第二弾 fixture では、管理 API と複数自治体境界の最終確認用に以下のデータを追加しています。

- 自治体マスタ: `目黒区`
- 支店マスタ: `目黒中央図書館`、`緑が丘図書館`
- 著者マスタ: `画面確認用 著者A`、`画面確認用 著者B`
- カテゴリマスタ: `地域資料`、`科学`
- 書籍マスタ: `管理画面確認用 地域資料`、`管理画面確認用 科学入門`、`自治体境界確認用 共通所蔵本`
- 目黒区側の職員、利用者、休館日、貸出中、取り置き中予約、保存済み検索条件

代表確認シナリオは以下です。

```console
curl "http://127.0.0.1:8000/bookman/api/municipalities/"
curl "http://127.0.0.1:8000/bookman/api/branches/?municipality=2"
curl "http://127.0.0.1:8000/bookman/api/books/?municipality=1"
curl "http://127.0.0.1:8000/bookman/api/books/?municipality=2"
curl "http://127.0.0.1:8000/bookman/api/branch-book-stocks/?municipality=2"
curl "http://127.0.0.1:8000/bookman/api/staff/?municipality=2"
curl "http://127.0.0.1:8000/bookman/api/lendings/?municipality=2"
curl "http://127.0.0.1:8000/bookman/api/reservations/?municipality=2"
curl "http://127.0.0.1:8000/bookman/api/authors/"
curl "http://127.0.0.1:8000/bookman/api/categories/"
```

`自治体境界確認用 共通所蔵本` は渋谷区と目黒区の両方に所蔵を持ちます。`municipality=1` と `municipality=2` で書籍一覧を見比べ、`total_amount` と `branch_stocks` が選択自治体の支店だけで集計されることを確認してください。

## サーバーの起動

Bookman はフロントエンドとバックエンドを両方起動して動かします。

ターミナル 1 でバックエンドを起動します。

```console
cd ../bookman_backend
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

ターミナル 2 でフロントエンドの開発用サーバーを起動します。

```console
cd ../bookman_nextjs
npm run dev
```

ブラウザで http://localhost:3000 を開きます。

## API

通常の開発では、フロントエンドは以下の Django API を参照します。

- `http://127.0.0.1:8000/bookman/api/branches/`
- `http://127.0.0.1:8000/bookman/api/books/`

API だけを直接確認する場合は、バックエンド起動後にブラウザまたは curl でアクセスします。

```console
curl http://127.0.0.1:8000/bookman/api/branches/
curl http://127.0.0.1:8000/bookman/api/books/
```

フロントエンド側の接続先は `bookman_nextjs` の `BOOKMAN_API_BASE_URL` で変更できます。

## テストと検証

通常は Codex に「テスト実行して」「migration まで確認して」と依頼すれば十分です。

手元で実行する場合は、以下を使います。

```console
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

DB へ migration を適用できるか確認する場合は、MySQL 接続情報が正しい状態で実行します。

```console
python manage.py migrate --noinput
```
