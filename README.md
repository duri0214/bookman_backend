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

初期データを読み込みます。

```console
python manage.py loaddata bookman/fixtures/m_branch-data.json
python manage.py loaddata bookman/fixtures/m_category-data.json
python manage.py loaddata bookman/fixtures/author-data.json
python manage.py loaddata bookman/fixtures/book-data.json
```

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
