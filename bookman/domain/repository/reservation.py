from datetime import timedelta

from django.utils import timezone

from bookman.models import BranchBookStock, Customer, Reservation


RESERVATION_HOLD_DAYS = 7


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
