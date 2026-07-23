from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from bookman.models import (
    Author,
    Book,
    Branch,
    BranchBookStock,
    BranchClosedDay,
    Category,
    Customer,
    Lending,
    LibraryStaff,
    Reservation,
)


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
        cls.customer = Customer.objects.create(
            name="山田太郎",
            phone="090-0000-0000",
            max_lending_count=2,
        )
        cls.second_customer = Customer.objects.create(
            name="佐藤花子",
            phone="090-0000-0001",
            max_lending_count=2,
        )
        cls.contact_staff = LibraryStaff.objects.create(
            name="貸出担当者",
            branch=cls.branch,
            role="counter",
        )

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

    def assert_business_error_response(self, response, *, code, message):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "code": code,
                "message": message,
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
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

    def test_branch_closed_day_create_list_and_delete(self):
        """
        シナリオ:
        - 入力: 支店ID、休館日、理由を含む休館日登録ペイロード。
        - 処理: 休館日APIへPOSTし、支店で絞り込んだ一覧GET後にDELETEする。
        - 期待値: 休館日が登録・一覧表示され、削除後は対象支店の休館日が残らないこと。
        """
        payload = {
            "branch": self.branch.id,
            "date": "2026-01-15",
            "reason": "蔵書点検",
        }

        response = self.client.post(
            "/bookman/api/branch-closed-days/",
            payload,
            format="json",
        )
        list_response = self.client.get(
            f"/bookman/api/branch-closed-days/?branch={self.branch.id}"
        )
        delete_response = self.client.delete(
            f"/bookman/api/branch-closed-days/{response.data['id']}/"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["branch_name"], "中央図書館")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]["reason"], "蔵書点検")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BranchClosedDay.objects.filter(branch=self.branch).exists())

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
        self.assertEqual(response.data[0]["available_amount"], 2)

    def test_branch_book_stock_list_returns_available_amount(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数2冊のうち1冊が貸出中の状態。
        - 処理: 所蔵数一覧APIへGETリクエストする。
        - 期待値: amount は総所蔵数2、available_amount は貸出中1冊を差し引いた1で返ること。
        """
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )

        response = self.client.get("/bookman/api/branch-book-stocks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["amount"], 2)
        self.assertEqual(response.data[0]["available_amount"], 1)

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
        lending = Lending.objects.create(
            branch_book_stock=self.branch_stock,
            return_date=date(2026, 1, 15),
            customer=self.customer,
            contact_staff=self.contact_staff,
        )

        self.assertEqual(lending.branch_book_stock, self.branch_stock)
        self.assertTrue(lending.active)

    def test_customer_list_endpoint_accepts_create_request(self):
        """
        シナリオ:
        - 入力: 利用者登録ペイロード。
        - 処理: 利用者一覧APIへPOSTリクエストする。
        - 期待値: 利用者が作成され、貸出上限冊数がレスポンスに返ること。
        """
        response = self.client.post(
            "/bookman/api/customers/",
            {
                "name": "鈴木一郎",
                "phone": "090-0000-0002",
                "max_lending_count": 3,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["max_lending_count"], 3)
        self.assertTrue(Customer.objects.filter(name="鈴木一郎").exists())

    def test_staff_list_returns_business_staff_fields(self):
        """
        シナリオ:
        - 入力: 職員データが登録されている状態。
        - 処理: 職員一覧APIへGETリクエストする。
        - 期待値: 職員ID、職員名、所属支店、権限種別が返ること。
        """
        response = self.client.get("/bookman/api/staff/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": self.contact_staff.id,
                    "name": "貸出担当者",
                    "branch": self.branch.id,
                    "role": "counter",
                }
            ],
        )

    def test_lending_create_accepts_available_stock(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数が2冊あり、利用者がまだ対象書籍を借りていない状態。
        - 処理: 貸出APIへ貸出登録リクエストをPOSTする。
        - 期待値: 貸出情報が作成され、active が True で返ること。
        """
        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-15",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["active"])
        self.assertEqual(response.data["customer_name"], "山田太郎")
        self.assertEqual(response.data["contact_staff_name"], "貸出担当者")
        self.assertEqual(response.data["return_date"], "2026-01-15")
        self.assertEqual(response.data["original_return_date"], "2026-01-15")
        self.assertFalse(response.data["return_date_adjusted"])
        self.assertEqual(response.data["return_date_adjustment_reason"], "")
        self.assertTrue(
            Lending.objects.filter(
                branch_book_stock=self.branch_stock,
                customer=self.customer,
                active=True,
            ).exists()
        )

    def test_lending_create_adjusts_return_date_for_branch_closed_days(self):
        """
        シナリオ:
        - 入力: 返却予定日から2日連続で同じ支店の休館日が登録されている状態。
        - 処理: 休館日に当たる返却予定日で貸出APIへPOSTする。
        - 期待値: 返却予定日が次の開館日へ繰り延べられ、補正前日付と休館理由が返ること。
        """
        BranchClosedDay.objects.create(
            branch=self.branch,
            date=date(2026, 1, 15),
            reason="祝日",
        )
        BranchClosedDay.objects.create(
            branch=self.branch,
            date=date(2026, 1, 16),
            reason="蔵書点検",
        )

        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-15",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["return_date"], "2026-01-17")
        self.assertEqual(response.data["original_return_date"], "2026-01-15")
        self.assertTrue(response.data["return_date_adjusted"])
        self.assertEqual(
            response.data["return_date_adjustment_reason"],
            "祝日、蔵書点検",
        )
        lending = Lending.objects.get(id=response.data["id"])
        self.assertEqual(lending.return_date, date(2026, 1, 17))

    def test_lending_create_ignores_other_branch_closed_day(self):
        """
        シナリオ:
        - 入力: 別支店だけに休館日が登録されている状態。
        - 処理: 通常営業日の対象支店で貸出APIへPOSTする。
        - 期待値: 返却予定日は補正されず、補正フラグが False で返ること。
        """
        BranchClosedDay.objects.create(
            branch=self.second_branch,
            date=date(2026, 1, 15),
            reason="臨時休館",
        )

        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-15",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["return_date"], "2026-01-15")
        self.assertFalse(response.data["return_date_adjusted"])

    def test_lending_create_rejects_duplicate_book_for_same_customer(self):
        """
        シナリオ:
        - 入力: 利用者が同じ本をすでに貸出中の状態。
        - 処理: 同じ支店別所蔵に対して貸出APIへPOSTする。
        - 期待値: 重複貸出コード付きの400が返り、同じ利用者に2件目の貸出が作成されないこと。
        """
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )

        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-16",
            },
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="duplicate_book_lending",
            message="同じ利用者は同じ本を2冊以上借りられません。",
        )
        self.assertEqual(
            Lending.objects.filter(customer=self.customer, active=True).count(),
            1,
        )

    def test_lending_create_rejects_unavailable_stock_for_other_customer(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数2冊がすべて別利用者へ貸出中の状態。
        - 処理: さらに別利用者で貸出APIへPOSTする。
        - 期待値: 在庫不足コード付きの400が返り、在庫数を超える貸出が作成されないこと。
        """
        third_customer = Customer.objects.create(name="田中次郎")
        for index in range(2):
            Lending.objects.create(
                branch_book_stock=self.branch_stock,
                customer=Customer.objects.create(name=f"貸出利用者{index}"),
                contact_staff=self.contact_staff,
                return_date=date(2026, 1, 15),
            )

        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": third_customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-16",
            },
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="lending_stock_unavailable",
            message="対象の本は貸出可能冊数が残っていません。",
        )
        self.assertEqual(
            Lending.objects.filter(branch_book_stock=self.branch_stock).count(),
            2,
        )

    def test_lending_create_rejects_customer_lending_limit(self):
        """
        シナリオ:
        - 入力: 利用者の貸出上限2冊に達している状態。
        - 処理: 別の本で貸出APIへPOSTする。
        - 期待値: 貸出上限超過コード付きの400が返り、上限を超える貸出が作成されないこと。
        """
        second_book = Book.objects.create(
            name="銀河鉄道の夜",
            category=self.category,
            lead_text="童話です。",
            isbn="9780000000004",
            publication_date=date(2026, 1, 4),
        )
        third_book = Book.objects.create(
            name="注文の多い料理店",
            category=self.category,
            lead_text="童話集です。",
            isbn="9780000000005",
            publication_date=date(2026, 1, 5),
        )
        second_book.authors.set([self.author])
        third_book.authors.set([self.author])
        second_stock = BranchBookStock.objects.create(
            branch=self.branch,
            book=second_book,
            amount=1,
        )
        third_stock = BranchBookStock.objects.create(
            branch=self.branch,
            book=third_book,
            amount=1,
        )
        for stock in [self.branch_stock, second_stock]:
            Lending.objects.create(
                branch_book_stock=stock,
                customer=self.customer,
                contact_staff=self.contact_staff,
                return_date=date(2026, 1, 15),
            )

        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": third_stock.id,
                "customer": self.customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-16",
            },
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="customer_lending_limit_exceeded",
            message="利用者の貸出上限冊数に達しています。",
        )
        self.assertEqual(
            Lending.objects.filter(customer=self.customer, active=True).count(),
            2,
        )

    def test_lending_create_fulfills_held_reservation(self):
        """
        シナリオ:
        - 入力: 1冊が貸出中、1冊が対象利用者へ取り置き中の支店別所蔵。
        - 処理: 取り置き中の利用者で貸出APIへPOSTする。
        - 期待値: 貸出情報が作成され、取り置き予約が fulfilled へ更新されること。
        """
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )
        reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.second_customer,
            status=Reservation.Status.HELD,
            hold_expires_on=date(2026, 1, 22),
        )

        response = self.client.post(
            "/bookman/api/lendings/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.second_customer.id,
                "contact_staff": self.contact_staff.id,
                "return_date": "2026-01-16",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.FULFILLED)
        self.assertIsNone(reservation.hold_expires_on)

    def test_lending_return_marks_lending_inactive(self):
        """
        シナリオ:
        - 入力: 貸出中の貸出情報が1件ある状態。
        - 処理: 返却APIへ貸出IDをPOSTする。
        - 期待値: active が False に更新され、返却済みの貸出情報が返ること。
        """
        lending = Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )

        response = self.client.post(
            "/bookman/api/lendings/return/",
            {"lending": lending.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lending.refresh_from_db()
        self.assertFalse(lending.active)
        self.assertFalse(response.data["returned_lending"]["active"])
        self.assertIsNone(response.data["held_reservation"])

    def test_reservation_create_accepts_unavailable_stock(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数2冊がすべて貸出中で、別利用者が未予約の状態。
        - 処理: 予約一覧APIへ予約登録リクエストをPOSTする。
        - 期待値: 予約待ち状態の予約が作成され、一覧APIでも表示用名称つきで返ること。
        """
        reserve_customer = Customer.objects.create(name="予約利用者")
        for index in range(2):
            Lending.objects.create(
                branch_book_stock=self.branch_stock,
                customer=Customer.objects.create(name=f"貸出中利用者{index}"),
                contact_staff=self.contact_staff,
                return_date=date(2026, 1, 15),
            )

        response = self.client.post(
            "/bookman/api/reservations/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": reserve_customer.id,
            },
            format="json",
        )
        list_response = self.client.get("/bookman/api/reservations/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Reservation.Status.WAITING)
        self.assertEqual(response.data["customer_name"], "予約利用者")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]["book_name"], "吾輩は猫である")

    def test_reservation_create_rejects_available_stock(self):
        """
        シナリオ:
        - 入力: 貸出可能冊数が残っている支店別所蔵と利用者。
        - 処理: 予約一覧APIへ予約登録リクエストをPOSTする。
        - 期待値: 貸出可能な本は予約できないコード付きの400が返ること。
        """
        response = self.client.post(
            "/bookman/api/reservations/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
            },
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="reservation_stock_available",
            message="対象の本は貸出可能冊数が残っているため予約できません。",
        )

    def test_reservation_create_rejects_duplicate_open_reservation(self):
        """
        シナリオ:
        - 入力: 同じ利用者が同じ支店別所蔵へ予約待ちを持つ状態。
        - 処理: 予約一覧APIへ同じ予約登録リクエストをPOSTする。
        - 期待値: 重複予約コード付きの400が返り、未完了予約が増えないこと。
        """
        for index in range(2):
            Lending.objects.create(
                branch_book_stock=self.branch_stock,
                customer=Customer.objects.create(name=f"貸出利用者{index}"),
                contact_staff=self.contact_staff,
                return_date=date(2026, 1, 15),
            )
        Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
        )

        response = self.client.post(
            "/bookman/api/reservations/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
            },
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="duplicate_reservation",
            message="同じ利用者は同じ支店別所蔵へ重複して予約できません。",
        )
        self.assertEqual(
            Reservation.objects.filter(
                branch_book_stock=self.branch_stock,
                customer=self.customer,
                status=Reservation.Status.WAITING,
            ).count(),
            1,
        )

    def test_reservation_create_rejects_customer_lending_same_book(self):
        """
        シナリオ:
        - 入力: 利用者が同じ本をすでに貸出中で、同じ支店別所蔵の貸出可能冊数が0の状態。
        - 処理: 予約一覧APIへその利用者の予約登録リクエストをPOSTする。
        - 期待値: 同じ本を貸出中の利用者は予約できないコード付きの400が返り、予約が作成されないこと。
        """
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=Customer.objects.create(name="貸出中利用者"),
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )

        response = self.client.post(
            "/bookman/api/reservations/",
            {
                "branch_book_stock": self.branch_stock.id,
                "customer": self.customer.id,
            },
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="duplicate_book_reservation",
            message="同じ本を貸出中の利用者は予約できません。",
        )
        self.assertFalse(
            Reservation.objects.filter(
                branch_book_stock=self.branch_stock,
                customer=self.customer,
            ).exists()
        )

    def test_lending_return_holds_oldest_waiting_reservation(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数2冊が貸出中で、同じ支店に予約待ちが2件ある状態。
        - 処理: 返却APIへ先に作成した貸出IDをPOSTする。
        - 期待値: 返却貸出が inactive になり、最古の予約だけが取り置き中になってレスポンスに利用者情報が返ること。
        """
        lending = Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.second_customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )
        first_reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=Customer.objects.create(name="予約1番目"),
        )
        second_reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=Customer.objects.create(name="予約2番目"),
        )

        response = self.client.post(
            "/bookman/api/lendings/return/",
            {"lending": lending.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_reservation.refresh_from_db()
        second_reservation.refresh_from_db()
        self.assertEqual(first_reservation.status, Reservation.Status.HELD)
        self.assertIsNotNone(first_reservation.hold_expires_on)
        self.assertEqual(second_reservation.status, Reservation.Status.WAITING)
        self.assertEqual(
            response.data["held_reservation"]["customer_name"],
            "予約1番目",
        )

    def test_branch_book_stock_available_amount_excludes_held_reservation(self):
        """
        シナリオ:
        - 入力: 支店別所蔵数2冊のうち1冊が貸出中、1冊が取り置き中の状態。
        - 処理: 所蔵数一覧APIへGETリクエストする。
        - 期待値: available_amount は貸出中と取り置き中を差し引いた0で返ること。
        """
        Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
        )
        Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.second_customer,
            status=Reservation.Status.HELD,
            hold_expires_on=date(2026, 1, 22),
        )

        response = self.client.get("/bookman/api/branch-book-stocks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["available_amount"], 0)

    def test_reservation_cancel_promotes_next_waiting_reservation(self):
        """
        シナリオ:
        - 入力: 取り置き中の予約と次の予約待ちが同じ支店別所蔵にある状態。
        - 処理: 取り置き中予約の取消APIへPOSTする。
        - 期待値: 取消対象は canceled になり、次の予約待ちが held に進むこと。
        """
        held_reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            status=Reservation.Status.HELD,
            hold_expires_on=date(2026, 1, 22),
        )
        next_reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.second_customer,
        )

        response = self.client.post(
            f"/bookman/api/reservations/{held_reservation.id}/cancel/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        held_reservation.refresh_from_db()
        next_reservation.refresh_from_db()
        self.assertEqual(held_reservation.status, Reservation.Status.CANCELED)
        self.assertEqual(next_reservation.status, Reservation.Status.HELD)
        self.assertEqual(
            response.data["canceled_reservation"]["status"],
            Reservation.Status.CANCELED,
        )

    def test_reservation_cancel_rejects_finished_reservation(self):
        """
        シナリオ:
        - 入力: すでに期限切れになった予約。
        - 処理: 予約取消APIへPOSTする。
        - 期待値: 取消不可コード付きの400が返り、予約状態が変わらないこと。
        """
        reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            status=Reservation.Status.EXPIRED,
        )

        response = self.client.post(
            f"/bookman/api/reservations/{reservation.id}/cancel/",
            {},
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="reservation_not_cancelable",
            message="取消対象の予約は取り消しできない状態です。",
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.EXPIRED)

    def test_reservation_expire_marks_due_holds_and_promotes_next(self):
        """
        シナリオ:
        - 入力: 期限日を過ぎた取り置きと、同じ支店別所蔵の次の予約待ちがある状態。
        - 処理: 取り置き期限切れ処理APIへPOSTする。
        - 期待値: 期限切れ対象は expired になり、次の予約待ちは held へ進むこと。
        """
        due_hold = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            status=Reservation.Status.HELD,
            hold_expires_on=timezone.localdate() - timedelta(days=1),
        )
        next_reservation = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.second_customer,
        )

        response = self.client.post(
            "/bookman/api/reservations/expire/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        due_hold.refresh_from_db()
        next_reservation.refresh_from_db()
        self.assertEqual(response.data["expired_count"], 1)
        self.assertEqual(due_hold.status, Reservation.Status.EXPIRED)
        self.assertEqual(next_reservation.status, Reservation.Status.HELD)

    def test_reservation_expire_promotes_waiting_reservations_for_each_expired_hold(
        self,
    ):
        """
        シナリオ:
        - 入力: 同じ支店別所蔵で期限日を過ぎた取り置きが2件、次の予約待ちが2件ある状態。
        - 処理: 取り置き期限切れ処理APIへPOSTする。
        - 期待値: 期限切れ対象2件が expired になり、空いた冊数分の予約待ち2件が held へ進むこと。
        """
        first_due_hold = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            status=Reservation.Status.HELD,
            hold_expires_on=timezone.localdate() - timedelta(days=1),
        )
        second_due_hold = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.second_customer,
            status=Reservation.Status.HELD,
            hold_expires_on=timezone.localdate() - timedelta(days=1),
        )
        first_waiting = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=Customer.objects.create(name="期限切れ後予約1番目"),
        )
        second_waiting = Reservation.objects.create(
            branch_book_stock=self.branch_stock,
            customer=Customer.objects.create(name="期限切れ後予約2番目"),
        )

        response = self.client.post(
            "/bookman/api/reservations/expire/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_due_hold.refresh_from_db()
        second_due_hold.refresh_from_db()
        first_waiting.refresh_from_db()
        second_waiting.refresh_from_db()
        self.assertEqual(response.data["expired_count"], 2)
        self.assertEqual(first_due_hold.status, Reservation.Status.EXPIRED)
        self.assertEqual(second_due_hold.status, Reservation.Status.EXPIRED)
        self.assertEqual(first_waiting.status, Reservation.Status.HELD)
        self.assertEqual(second_waiting.status, Reservation.Status.HELD)

    def test_lending_return_rejects_already_returned_lending(self):
        """
        シナリオ:
        - 入力: 返却済みの貸出情報が1件ある状態。
        - 処理: 返却APIへ同じ貸出IDをPOSTする。
        - 期待値: 返却済みコード付きの400が返り、返却済み状態のまま変わらないこと。
        """
        lending = Lending.objects.create(
            branch_book_stock=self.branch_stock,
            customer=self.customer,
            contact_staff=self.contact_staff,
            return_date=date(2026, 1, 15),
            active=False,
        )

        response = self.client.post(
            "/bookman/api/lendings/return/",
            {"lending": lending.id},
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="lending_already_returned",
            message="返却対象の貸出情報はすでに返却済みです。",
        )
        lending.refresh_from_db()
        self.assertFalse(lending.active)

    def test_lending_return_rejects_missing_lending(self):
        """
        シナリオ:
        - 入力: 存在しない貸出IDを指定した返却ペイロード。
        - 処理: 返却APIへPOSTリクエストする。
        - 期待値: 貸出未存在コード付きの400が返ること。
        """
        response = self.client.post(
            "/bookman/api/lendings/return/",
            {"lending": 999999},
            format="json",
        )

        self.assert_business_error_response(
            response,
            code="lending_not_found",
            message="返却対象の貸出情報が見つかりません。",
        )

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
