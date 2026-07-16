# Bookman - 図書管理ソフト
https://qiita.com/YoshitakaOkada/items/570c025cf235062649c8

## Codex 運用

このリポジトリは、同階層にある `portfolio/.codex` を Codex 運用ルールとスキルの管理元として参照します。

```text
dev/
  portfolio/
  bookman_backend/
  bookman_nextjs/
```

詳細は `.codex/README.md` と `AGENTS.md` を参照してください。

## fixtures
```console
python manage.py loaddata bookman/fixtures/m_branch-data.json
python manage.py loaddata bookman/fixtures/m_category-data.json
python manage.py loaddata bookman/fixtures/author-data.json
python manage.py loaddata bookman/fixtures/book-data.json
```

## migration
```console
python manage.py makemigrations bookman
python manage.py migrate
```
