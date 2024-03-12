# Bookman - 図書管理ソフト
https://qiita.com/YoshitakaOkada/items/570c025cf235062649c8

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