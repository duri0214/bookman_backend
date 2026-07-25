from django.utils import timezone

from bookman.models import Book, BranchBookStock, Customer, Lending, LibraryStaff


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

    def exists_active_book_by_customer_in_municipality(
        self,
        *,
        customer: Customer,
        book: Book,
        municipality_id: int,
    ) -> bool:
        """
        指定利用者が同じ自治体内で同じ書籍を貸出中かどうかを返す。
        """
        return Lending.objects.filter(
            customer=customer,
            branch_book_stock__book=book,
            branch_book_stock__branch__municipality_id=municipality_id,
            active=True,
        ).exists()

    def create(
        self,
        *,
        stock: BranchBookStock,
        customer: Customer,
        contact_staff: LibraryStaff,
        return_date,
        original_return_date,
        return_date_adjustment_reason: str,
    ) -> Lending:
        """
        貸出情報を作成する。
        """
        return Lending.objects.create(
            branch_book_stock=stock,
            customer=customer,
            contact_staff=contact_staff,
            return_date=return_date,
            original_return_date=original_return_date,
            return_date_adjustment_reason=return_date_adjustment_reason,
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
