from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from bookman.models import Author, Book, Branch, Category


class BookmanApiTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(
            name="中央図書館",
            address="青森県上北郡六戸町",
            phone="0176-00-0000",
            remark="本館",
        )
        cls.category = Category.objects.create(name="小説", color="#ff0000")
        cls.second_category = Category.objects.create(name="実用書", color="#00ff00")
        cls.author = Author.objects.create(name="夏目漱石")
        cls.second_author = Author.objects.create(name="宮沢賢治")

        cls.book = Book.objects.create(
            name="吾輩は猫である",
            category=cls.category,
            lead_text="近代文学の代表作です。",
            amount=3,
            isbn="9780000000001",
            publication_date=date(2026, 1, 1),
        )
        cls.book.authors.set([cls.author])

    def test_branch_list_returns_frontend_fields(self):
        """
        シナリオ:
        - 入力: 支店データが1件登録されている状態。
        - 処理: 支店一覧APIへGETリクエストする。
        - 期待値: フロントエンドが利用する支店フィールドがID順で返ること。
        """
        response = self.client.get("/bookman/api/branches/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": self.branch.id,
                    "name": "中央図書館",
                    "address": "青森県上北郡六戸町",
                    "phone": "0176-00-0000",
                    "remark": "本館",
                }
            ],
        )

    def test_branch_list_endpoint_accepts_create_request(self):
        """
        シナリオ:
        - 入力: フロントエンドと同じ支店登録ペイロード。
        - 処理: 支店一覧と同じURLへPOSTリクエストする。
        - 期待値: 支店が作成され、レスポンスに支店フィールドが返ること。
        """
        payload = {
            "name": "東図書館",
            "address": "青森県上北郡六戸町東",
            "phone": "0176-00-0001",
            "remark": "分館",
        }

        response = self.client.post("/bookman/api/branches/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "東図書館")
        self.assertTrue(Branch.objects.filter(name="東図書館").exists())

    def test_book_list_returns_primary_key_relations(self):
        """
        シナリオ:
        - 入力: カテゴリと著者に紐づく書籍データが登録されている状態。
        - 処理: 書籍一覧APIへGETリクエストする。
        - 期待値: category はID、authors はID配列として返ること。
        """
        response = self.client.get("/bookman/api/books/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["category"], self.category.id)
        self.assertEqual(response.data[0]["authors"], [self.author.id])
        self.assertEqual(response.data[0]["lead_text"], "近代文学の代表作です。")

    def test_book_create_accepts_frontend_payload(self):
        """
        シナリオ:
        - 入力: フロントエンドと同じ書籍登録ペイロード。
        - 処理: 書籍登録APIへPOSTリクエストする。
        - 期待値: 書籍が作成され、著者の多対多関連も保存されること。
        """
        payload = {
            "name": "銀河鉄道の夜",
            "category": self.second_category.id,
            "authors": [self.second_author.id],
            "lead_text": "宮沢賢治の童話です。",
            "amount": 5,
            "isbn": "9780000000002",
            "publication_date": "2026-01-02",
        }

        response = self.client.post(
            "/bookman/api/books/create/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book = Book.objects.get(name="銀河鉄道の夜")
        self.assertEqual(book.category, self.second_category)
        self.assertEqual(
            list(book.authors.values_list("id", flat=True)), [self.second_author.id]
        )

    def test_book_detail_returns_frontend_fields(self):
        """
        シナリオ:
        - 入力: 書籍データが1件登録されている状態。
        - 処理: 書籍詳細APIへGETリクエストする。
        - 期待値: 一覧と同じフィールド契約で対象書籍が返ること。
        """
        response = self.client.get(f"/bookman/api/books/{self.book.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.book.id)
        self.assertEqual(response.data["category"], self.category.id)
        self.assertEqual(response.data["authors"], [self.author.id])

    def test_author_and_category_lists_are_ordered_by_id(self):
        """
        シナリオ:
        - 入力: 著者とカテゴリが複数登録されている状態。
        - 処理: 著者一覧APIとカテゴリ一覧APIへGETリクエストする。
        - 期待値: どちらもID順で、フロントエンドが利用するフィールドが返ること。
        """
        author_response = self.client.get("/bookman/api/authors/")
        category_response = self.client.get("/bookman/api/categories/")

        self.assertEqual(author_response.status_code, status.HTTP_200_OK)
        self.assertEqual(category_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [author["id"] for author in author_response.data],
            [self.author.id, self.second_author.id],
        )
        self.assertEqual(
            [category["id"] for category in category_response.data],
            [self.category.id, self.second_category.id],
        )
