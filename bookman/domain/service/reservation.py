from django.db import transaction

from bookman.domain.repository import (
    BranchBookStockRepository,
    LendingRepository,
    ReservationRepository,
)
from bookman.domain.service.errors import (
    DuplicateBookReservationError,
    DuplicateReservationError,
    LendingStockUnavailableError,
    ReservationMunicipalityMismatchError,
    ReservationNotCancelableError,
    ReservationNotFoundError,
    ReservationStockAvailableError,
)
from bookman.domain.valueobject import ReservationRegistrationInput
from bookman.models import BranchBookStock, Reservation


class ReservationService:
    """
    予約登録、取消、取り置き期限切れを扱う業務処理。
    """

    def __init__(
        self,
        stock_repository: BranchBookStockRepository | None = None,
        lending_repository: LendingRepository | None = None,
        reservation_repository: ReservationRepository | None = None,
    ):
        self.stock_repository = stock_repository or BranchBookStockRepository()
        self.lending_repository = lending_repository or LendingRepository()
        self.reservation_repository = reservation_repository or ReservationRepository()

    def validate_registration(
        self,
        reservation_input: ReservationRegistrationInput,
    ) -> None:
        """
        予約対象の自治体スコープを検証する。
        """
        if (
            reservation_input.selected_municipality is not None
            and reservation_input.branch_book_stock.branch.municipality_id
            != reservation_input.selected_municipality.id
        ):
            raise ReservationMunicipalityMismatchError

    def reserve(self, reservation_input: ReservationRegistrationInput) -> Reservation:
        """
        貸出可能冊数がない支店別所蔵へ予約待ちを登録する。
        """
        self.validate_registration(reservation_input)

        with transaction.atomic():
            stock = self.stock_repository.get_for_update(
                reservation_input.branch_book_stock.book,
                reservation_input.branch_book_stock.branch,
            )
            if stock is None:
                raise LendingStockUnavailableError

            if self.reservation_repository.exists_open_by_customer_and_stock(
                stock=stock,
                customer=reservation_input.customer,
            ):
                raise DuplicateReservationError

            municipality_id = stock.branch.municipality_id
            if self.lending_repository.exists_active_book_by_customer_in_municipality(
                customer=reservation_input.customer,
                book=stock.book,
                municipality_id=municipality_id,
            ):
                raise DuplicateBookReservationError

            active_stock_count = self.lending_repository.count_active_by_stock(stock)
            held_stock_count = self.reservation_repository.count_held_by_stock(stock)
            if active_stock_count + held_stock_count < stock.amount:
                raise ReservationStockAvailableError

            return self.reservation_repository.create_waiting(
                stock=stock,
                customer=reservation_input.customer,
            )

    def cancel(self, *, reservation_id: int, selected_municipality=None) -> Reservation:
        """
        選択中自治体内の予約待ちまたは取り置き中の予約を取り消す。
        """
        with transaction.atomic():
            reservation = self.reservation_repository.get_for_update(reservation_id)
            if reservation is None:
                raise ReservationNotFoundError

            if (
                selected_municipality is not None
                and reservation.branch_book_stock.branch.municipality_id
                != selected_municipality.id
            ):
                raise ReservationNotFoundError

            if reservation.status not in self.reservation_repository.open_statuses:
                raise ReservationNotCancelableError

            was_held = reservation.status == Reservation.Status.HELD
            self.reservation_repository.save_status(
                reservation,
                Reservation.Status.CANCELED,
            )
            if was_held:
                self._hold_next_waiting(reservation.branch_book_stock)

        return reservation

    def expire_due_holds(self, *, selected_municipality=None) -> list[Reservation]:
        """
        選択中自治体内で期限切れの取り置きを expired にし、次の予約を取り置きへ進める。
        """
        expired_reservations = []
        stocks_to_promote = []

        with transaction.atomic():
            due_holds = self.reservation_repository.list_due_holds_for_update(
                municipality=selected_municipality,
            )
            for reservation in due_holds:
                self.reservation_repository.save_status(
                    reservation,
                    Reservation.Status.EXPIRED,
                )
                expired_reservations.append(reservation)
                stocks_to_promote.append(reservation.branch_book_stock)

            for stock in stocks_to_promote:
                self._hold_next_waiting(stock)

        return expired_reservations

    def _hold_next_waiting(self, stock: BranchBookStock) -> Reservation | None:
        """
        指定支店別所蔵の次の予約待ちを取り置きへ進める。
        """
        next_reservation = self.reservation_repository.get_next_waiting_for_update(
            stock
        )
        if next_reservation is None:
            return None

        self.reservation_repository.hold(next_reservation)
        return next_reservation
