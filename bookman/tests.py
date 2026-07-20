from datetime import date

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from bookman.models import Author, Book, Branch, BranchBookStock, Category, Lending


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
        cls.branch_stock = BranchBookStock.objects.create(
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

    def test_book_list_returns_branch_stock_total_amount(self):
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
            response.data[0]["branch_stocks"],
            [
                {
                    "id": self.branch_stock.id,
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
        self.assertEqual(response.data["branch_stocks"][0]["amount"], 2)

    def test_book_detail_total_amount_sums_all_branch_stocks(self):
        """
        シナリオ:
        - 入力: 同じ書籍に複数支店の所蔵数が登録されている状態。
        - 処理: 書籍詳細APIへGETリクエストする。
        - 期待値: total_amount に全支店の BranchBookStock.amount 合計が返ること。
        """
        BranchBookStock.objects.create(
            branch=self.second_branch,
            book=self.book,
            amount=4,
        )

        response = self.client.get(f"/bookman/api/books/{self.book.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_amount"], 6)

    def test_branch_book_stock_list_returns_branch_book_amounts(self):
        """
        シナリオ:
        - 入力: 書籍と支店に紐づく所蔵数データが登録されている状態。
        - 処理: 所蔵数一覧APIへGETリクエストする。
        - 期待値: 支店ID、書籍ID、支店別数量が返り、書籍の総数量と区別できること。
        """
        response = self.client.get("/bookman/api/branch-book-stocks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["branch"], self.branch.id)
        self.assertEqual(response.data[0]["branch_name"], "中央図書館")
        self.assertEqual(response.data[0]["book"], self.book.id)
        self.assertEqual(response.data[0]["book_name"], "吾輩は猫である")
        self.assertEqual(response.data[0]["amount"], 2)

    def test_branch_book_stock_create_changes_book_total_amount_without_sync(self):
        """
        シナリオ:
        - 入力: 既存書籍と別支店に紐づく支店別所蔵数の登録ペイロード。
        - 処理: 所蔵数一覧APIへPOSTリクエストした後、書籍詳細APIへGETリクエストする。
        - 期待値: BranchBookStock が作成され、total_amount が同期処理なしで合計値に変わること。
        """
        payload = {
            "branch": self.second_branch.id,
            "book": self.book.id,
            "amount": 1,
        }

        response = self.client.post(
            "/bookman/api/branch-book-stocks/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            BranchBookStock.objects.filter(
                branch=self.second_branch, book=self.book, amount=1
            ).exists()
        )
        detail_response = self.client.get(f"/bookman/api/books/{self.book.id}/")
        self.assertEqual(detail_response.data["total_amount"], 3)

    def test_branch_book_stock_detail_accepts_amount_update(self):
        """
        シナリオ:
        - 入力: 登録済みの支店別所蔵数と更新後数量。
        - 処理: 所蔵数詳細APIへPATCHリクエストする。
        - 期待値: 対象 BranchBookStock の数量だけが更新されること。
        """
        response = self.client.patch(
            f"/bookman/api/branch-book-stocks/{self.branch_stock.id}/",
            {"amount": 3},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.branch_stock.refresh_from_db()
        self.assertEqual(self.branch_stock.amount, 3)

    def test_branch_book_stock_transfer_creates_destination_stock(self):
        """
        シナリオ:
        - 入力: 移動元に2冊あり、移動先には対象書籍の所蔵行がない状態。
        - 処理: 支店間移動APIへ1冊の移動リクエストをPOSTする。
        - 期待値: 移動元が1冊減り、移動先の所蔵行が1冊で作成されること。
        """
        payload = {
            "book": self.book.id,
            "from_branch": self.branch.id,
            "to_branch": self.second_branch.id,
            "amount": 1,
        }

        response = self.client.post(
            "/bookman/api/branch-book-stocks/transfer/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.branch_stock.refresh_from_db()
        destination_stock = BranchBookStock.objects.get(
            book=self.book, branch=self.second_branch
        )
        self.assertEqual(self.branch_stock.amount, 1)
        self.assertEqual(destination_stock.amount, 1)
        self.assertEqual(response.data["source_stock"]["amount"], 1)
        self.assertEqual(response.data["destination_stock"]["amount"], 1)

    def test_branch_book_stock_transfer_adds_existing_destination_stock(self):
        """
        シナリオ:
        - 入力: 移動元に2冊、移動先に同じ書籍が4冊ある状態。
        - 処理: 支店間移動APIへ2冊の移動リクエストをPOSTする。
        - 期待値: 移動元が0冊、移動先が6冊になり、書籍全体の所蔵数は変わらないこと。
        """
        destination_stock = BranchBookStock.objects.create(
            branch=self.second_branch,
            book=self.book,
            amount=4,
        )

        response = self.client.post(
            "/bookman/api/branch-book-stocks/transfer/",
            {
                "book": self.book.id,
                "from_branch": self.branch.id,
                "to_branch": self.second_branch.id,
                "amount": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.branch_stock.refresh_from_db()
        destination_stock.refresh_from_db()
        detail_response = self.client.get(f"/bookman/api/books/{self.book.id}/")
        self.assertEqual(self.branch_stock.amount, 0)
        self.assertEqual(destination_stock.amount, 6)
        self.assertEqual(detail_response.data["total_amount"], 6)

    def test_branch_book_stock_transfer_rejects_same_branch(self):
        """
        シナリオ:
        - 入力: 移動元と移動先に同じ支店を指定した移動ペイロード。
        - 処理: 支店間移動APIへPOSTリクエストする。
        - 期待値: 400 が返り、所蔵数が変更されないこと。
        """
        response = self.client.post(
            "/bookman/api/branch-book-stocks/transfer/",
            {
                "book": self.book.id,
                "from_branch": self.branch.id,
                "to_branch": self.branch.id,
                "amount": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.branch_stock.refresh_from_db()
        self.assertEqual(self.branch_stock.amount, 2)

    def test_branch_book_stock_transfer_rejects_zero_amount(self):
        """
        シナリオ:
        - 入力: 移動冊数に0を指定した移動ペイロード。
        - 処理: 支店間移動APIへPOSTリクエストする。
        - 期待値: 400 が返り、所蔵数が変更されないこと。
        """
        response = self.client.post(
            "/bookman/api/branch-book-stocks/transfer/",
            {
                "book": self.book.id,
                "from_branch": self.branch.id,
                "to_branch": self.second_branch.id,
                "amount": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.branch_stock.refresh_from_db()
        self.assertEqual(self.branch_stock.amount, 2)

    def test_branch_book_stock_transfer_rejects_insufficient_stock(self):
        """
        シナリオ:
        - 入力: 移動元の所蔵数2冊を超える3冊の移動ペイロード。
        - 処理: 支店間移動APIへPOSTリクエストする。
        - 期待値: 400 が返り、移動先の所蔵行が作成されないこと。
        """
        response = self.client.post(
            "/bookman/api/branch-book-stocks/transfer/",
            {
                "book": self.book.id,
                "from_branch": self.branch.id,
                "to_branch": self.second_branch.id,
                "amount": 3,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.branch_stock.refresh_from_db()
        self.assertEqual(self.branch_stock.amount, 2)
        self.assertFalse(
            BranchBookStock.objects.filter(
                book=self.book, branch=self.second_branch
            ).exists()
        )

    def test_branch_book_stock_transfer_rejects_missing_source_stock(self):
        """
        シナリオ:
        - 入力: 移動元に対象書籍の所蔵行がない移動ペイロード。
        - 処理: 支店間移動APIへPOSTリクエストする。
        - 期待値: 400 が返り、移動先の所蔵行が作成されないこと。
        """
        other_book = Book.objects.create(
            name="こころ",
            category=self.category,
            lead_text="近代文学です。",
            isbn="9780000000003",
            publication_date=date(2026, 1, 3),
        )
        other_book.authors.set([self.author])

        response = self.client.post(
            "/bookman/api/branch-book-stocks/transfer/",
            {
                "book": other_book.id,
                "from_branch": self.branch.id,
                "to_branch": self.second_branch.id,
                "amount": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            BranchBookStock.objects.filter(
                book=other_book, branch=self.second_branch
            ).exists()
        )

    def test_lending_belongs_to_branch_book_stock(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数と利用者、対応者が登録されている状態。
        - 処理: 支店別所蔵数に紐づく貸出情報を作成する。
        - 期待値: 貸出情報から対象の支店別所蔵数を参照でき、active の初期値が True になること。
        """
        customer_user = User.objects.create_user(username="customer")
        contact_user = User.objects.create_user(username="contact")

        lending = Lending.objects.create(
            branch_book_stock=self.branch_stock,
            return_date=date(2026, 1, 15),
            customer_user=customer_user,
            contact_user=contact_user,
        )

        self.assertEqual(lending.branch_book_stock, self.branch_stock)
        self.assertTrue(lending.active)

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
