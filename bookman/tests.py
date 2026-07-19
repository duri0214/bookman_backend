from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from bookman.models import Assignment, Author, Book, Branch, Category


class BookmanApiTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(
            name="中央図書館",
            address="青森県上北郡六戸町",
            phone="0176-00-0000",
            remark="本館",
        )
        cls.second_branch = Branch.objects.create(
            name="東図書館",
            address="青森県上北郡六戸町東",
            phone="0176-00-0001",
            remark="分館",
        )
        cls.category = Category.objects.create(name="小説", color="#ff0000")
        cls.second_category = Category.objects.create(name="実用書", color="#00ff00")
        cls.author = Author.objects.create(name="夏目漱石")
        cls.second_author = Author.objects.create(name="宮沢賢治")

        cls.book = Book.objects.create(
            name="吾輩は猫である",
            category=cls.category,
            lead_text="近代文学の代表作です。",
            isbn="9780000000001",
            publication_date=date(2026, 1, 1),
        )
        cls.book.authors.set([cls.author])
        cls.assignment = Assignment.objects.create(
            branch=cls.branch,
            book=cls.book,
            amount=2,
        )

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
                },
                {
                    "id": self.second_branch.id,
                    "name": "東図書館",
                    "address": "青森県上北郡六戸町東",
                    "phone": "0176-00-0001",
                    "remark": "分館",
                },
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
            "name": "西図書館",
            "address": "青森県上北郡六戸町西",
            "phone": "0176-00-0002",
            "remark": "西分館",
        }

        response = self.client.post("/bookman/api/branches/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "西図書館")
        self.assertTrue(Branch.objects.filter(name="西図書館").exists())

    def test_book_list_returns_assignment_total_amount(self):
        """
        シナリオ:
        - 入力: カテゴリ、著者、支店別所蔵数に紐づく書籍データが登録されている状態。
        - 処理: 書籍一覧APIへGETリクエストする。
        - 期待値: category はID、authors はID配列、total_amount は支店別所蔵数の合計として返ること。
        """
        response = self.client.get("/bookman/api/books/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["category"], self.category.id)
        self.assertEqual(response.data[0]["authors"], [self.author.id])
        self.assertEqual(response.data[0]["total_amount"], 2)
        self.assertEqual(
            response.data[0]["assignments"],
            [
                {
                    "id": self.assignment.id,
                    "branch": self.branch.id,
                    "branch_name": "中央図書館",
                    "amount": 2,
                }
            ],
        )
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
            "isbn": "9780000000002",
            "publication_date": "2026-01-02",
        }

        response = self.client.post(
            "/bookman/api/books/create/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_amount"], 0)
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
        self.assertEqual(response.data["total_amount"], 2)
        self.assertEqual(response.data["assignments"][0]["amount"], 2)

    def test_book_detail_total_amount_sums_all_branch_assignments(self):
        """
        シナリオ:
        - 入力: 同じ書籍に複数支店の所蔵数が登録されている状態。
        - 処理: 書籍詳細APIへGETリクエストする。
        - 期待値: total_amount に全支店の Assignment.amount 合計が返ること。
        """
        Assignment.objects.create(
            branch=self.second_branch,
            book=self.book,
            amount=4,
        )

        response = self.client.get(f"/bookman/api/books/{self.book.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_amount"], 6)

    def test_assignment_list_returns_branch_book_amounts(self):
        """
        シナリオ:
        - 入力: 書籍と支店に紐づく所蔵数データが登録されている状態。
        - 処理: 所蔵数一覧APIへGETリクエストする。
        - 期待値: 支店ID、書籍ID、支店別数量が返り、書籍の総数量と区別できること。
        """
        response = self.client.get("/bookman/api/assignments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["branch"], self.branch.id)
        self.assertEqual(response.data[0]["branch_name"], "中央図書館")
        self.assertEqual(response.data[0]["book"], self.book.id)
        self.assertEqual(response.data[0]["book_name"], "吾輩は猫である")
        self.assertEqual(response.data[0]["amount"], 2)

    def test_assignment_create_changes_book_total_amount_without_sync(self):
        """
        シナリオ:
        - 入力: 既存書籍と別支店に紐づく支店別所蔵数の登録ペイロード。
        - 処理: 所蔵数一覧APIへPOSTリクエストした後、書籍詳細APIへGETリクエストする。
        - 期待値: Assignment が作成され、total_amount が同期処理なしで合計値に変わること。
        """
        payload = {
            "branch": self.second_branch.id,
            "book": self.book.id,
            "amount": 1,
        }

        response = self.client.post("/bookman/api/assignments/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Assignment.objects.filter(
                branch=self.second_branch, book=self.book, amount=1
            ).exists()
        )
        detail_response = self.client.get(f"/bookman/api/books/{self.book.id}/")
        self.assertEqual(detail_response.data["total_amount"], 3)

    def test_assignment_detail_accepts_amount_update(self):
        """
        シナリオ:
        - 入力: 登録済みの支店別所蔵数と更新後数量。
        - 処理: 所蔵数詳細APIへPATCHリクエストする。
        - 期待値: 対象 Assignment の数量だけが更新されること。
        """
        response = self.client.patch(
            f"/bookman/api/assignments/{self.assignment.id}/",
            {"amount": 3},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.amount, 3)

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
