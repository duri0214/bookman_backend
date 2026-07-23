from datetime import timedelta

from django.utils import timezone

from bookman.models import (
    Book,
    Branch,
    BranchBookStock,
    BranchClosedDay,
    Customer,
    Lending,
    LibraryStaff,
    Reservation,
)


RESERVATION_HOLD_DAYS = 7


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


class BranchClosedDayRepository:
    """
    支店休館日の永続化操作。
    """

    def get_by_branch_and_date(
        self,
        *,
        branch: Branch,
        closed_date,
    ) -> BranchClosedDay | None:
        """
        指定支店の指定日が休館日として登録されていれば返す。
        """
        try:
            return BranchClosedDay.objects.get(branch=branch, date=closed_date)
        except BranchClosedDay.DoesNotExist:
            return None


class ReservationRepository:
    """
    予約と取り置き状態の永続化操作。
    """

    open_statuses = [Reservation.Status.WAITING, Reservation.Status.HELD]

    def count_held_by_stock(self, stock: BranchBookStock) -> int:
        """
        指定された支店別所蔵で取り置き中の件数を返す。
        """
        return Reservation.objects.filter(
            branch_book_stock=stock,
            status=Reservation.Status.HELD,
        ).count()

    def exists_open_by_customer_and_stock(
        self,
        *,
        stock: BranchBookStock,
        customer: Customer,
    ) -> bool:
        """
        指定利用者が同じ支店別所蔵へ未完了の予約を持つかどうかを返す。
        """
        return Reservation.objects.filter(
            branch_book_stock=stock,
            customer=customer,
            status__in=self.open_statuses,
        ).exists()

    def create_waiting(
        self,
        *,
        stock: BranchBookStock,
        customer: Customer,
    ) -> Reservation:
        """
        予約待ち状態の予約を作成する。
        """
        return Reservation.objects.create(
            branch_book_stock=stock,
            customer=customer,
        )

    def get_for_update(self, reservation_id: int) -> Reservation | None:
        """
        更新対象の予約を行ロック付きで取得する。
        """
        try:
            return Reservation.objects.select_for_update().get(id=reservation_id)
        except Reservation.DoesNotExist:
            return None

    def get_next_waiting_for_update(
        self,
        stock: BranchBookStock,
    ) -> Reservation | None:
        """
        指定支店別所蔵の最古の予約待ちを行ロック付きで取得する。
        """
        return (
            Reservation.objects.select_for_update()
            .filter(branch_book_stock=stock, status=Reservation.Status.WAITING)
            .order_by("created_at", "id")
            .first()
        )

    def get_held_by_customer_for_update(
        self,
        *,
        stock: BranchBookStock,
        customer: Customer,
    ) -> Reservation | None:
        """
        指定利用者への取り置き中予約を行ロック付きで取得する。
        """
        return (
            Reservation.objects.select_for_update()
            .filter(
                branch_book_stock=stock,
                customer=customer,
                status=Reservation.Status.HELD,
            )
            .first()
        )

    def list_due_holds_for_update(self) -> list[Reservation]:
        """
        取り置き期限を過ぎた予約を行ロック付きで返す。
        """
        today = timezone.localdate()
        return list(
            Reservation.objects.select_for_update()
            .filter(
                status=Reservation.Status.HELD,
                hold_expires_on__lt=today,
            )
            .select_related("branch_book_stock")
            .order_by("branch_book_stock_id", "created_at", "id")
        )

    def hold(self, reservation: Reservation) -> None:
        """
        予約を取り置き中へ進め、取り置き期限日を設定する。
        """
        reservation.status = Reservation.Status.HELD
        reservation.hold_expires_on = timezone.localdate() + timedelta(
            days=RESERVATION_HOLD_DAYS
        )
        reservation.updated_at = timezone.localdate()
        Reservation.objects.bulk_update(
            [reservation],
            ["status", "hold_expires_on", "updated_at"],
        )

    def save_status(self, reservation: Reservation, status: str) -> None:
        """
        予約状態を更新する。
        """
        reservation.status = status
        if status != Reservation.Status.HELD:
            reservation.hold_expires_on = None

        reservation.updated_at = timezone.localdate()
        Reservation.objects.bulk_update(
            [reservation],
            ["status", "hold_expires_on", "updated_at"],
        )
