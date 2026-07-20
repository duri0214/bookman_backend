from django.utils import timezone

from bookman.models import Book, Branch, BranchBookStock, Customer, Lending


class BranchBookStockRepository:
    """
    支店別所蔵数の永続化操作。
    """

    def get_for_update(self, book: Book, branch: Branch) -> BranchBookStock | None:
        """
        更新対象の支店別所蔵数を行ロック付きで取得する。
        """
        try:
            return BranchBookStock.objects.select_for_update().get(
                book=book,
                branch=branch,
            )
        except BranchBookStock.DoesNotExist:
            return None

    def get_or_create_for_update(
        self, book: Book, branch: Branch
    ) -> tuple[BranchBookStock, bool]:
        """
        更新対象の支店別所蔵数を行ロック付きで取得し、存在しない場合は作成する。
        """
        return BranchBookStock.objects.select_for_update().get_or_create(
            book=book,
            branch=branch,
            defaults={"amount": 0},
        )

    def save(self, stock: BranchBookStock) -> None:
        """
        支店別所蔵数を保存する。
        """
        stock.updated_at = timezone.localdate()
        stock.save(update_fields=["amount", "updated_at"])

    def bulk_save(self, stocks: list[BranchBookStock]) -> None:
        """
        複数の支店別所蔵数をまとめて保存する。
        """
        updated_at = timezone.localdate()
        for stock in stocks:
            stock.updated_at = updated_at

        BranchBookStock.objects.bulk_update(stocks, ["amount", "updated_at"])


class LendingRepository:
    """
    貸出情報の永続化操作。
    """

    def count_active_by_stock(self, stock: BranchBookStock) -> int:
        """
        指定された支店別所蔵で貸出中の件数を返す。
        """
        return Lending.objects.filter(branch_book_stock=stock, active=True).count()

    def count_active_by_customer(self, customer: Customer) -> int:
        """
        指定された利用者が貸出中の件数を返す。
        """
        return Lending.objects.filter(customer=customer, active=True).count()

    def exists_active_book_by_customer(self, *, customer: Customer, book: Book) -> bool:
        """
        指定された利用者が同じ書籍を貸出中かどうかを返す。
        """
        return Lending.objects.filter(
            customer=customer,
            branch_book_stock__book=book,
            active=True,
        ).exists()

    def create(
        self,
        *,
        stock: BranchBookStock,
        customer: Customer,
        contact_user,
        return_date,
    ) -> Lending:
        """
        貸出情報を作成する。
        """
        return Lending.objects.create(
            branch_book_stock=stock,
            customer=customer,
            contact_user=contact_user,
            return_date=return_date,
        )

    def get_for_update(self, lending_id: int) -> Lending | None:
        """
        更新対象の貸出情報を行ロック付きで取得する。
        """
        try:
            return Lending.objects.select_for_update().get(id=lending_id)
        except Lending.DoesNotExist:
            return None

    def save(self, lending: Lending) -> None:
        """
        貸出情報を保存する。
        """
        lending.updated_at = timezone.localdate()
        Lending.objects.bulk_update([lending], ["active", "updated_at"])
