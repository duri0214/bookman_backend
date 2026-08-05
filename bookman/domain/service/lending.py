from datetime import date, timedelta

from django.db import transaction

from bookman.domain.repository import (
    BranchBookStockRepository,
    BranchClosedDayRepository,
    LendingRepository,
    ReservationRepository,
)
from bookman.domain.service.errors import (
    ContactStaffBranchRequiredError,
    ContactStaffMunicipalityMismatchError,
    CustomerLendingLimitExceededError,
    DuplicateBookLendingError,
    LendingAlreadyReturnedError,
    LendingMunicipalityMismatchError,
    LendingNotFoundError,
    LendingStockUnavailableError,
)
from bookman.domain.valueobject import LendingRegistrationInput, LendingReturn
from bookman.models import Branch, BranchBookStock, Lending, Reservation


class LendingService:
    """
    利用者への貸出と返却を扱う業務処理。
    """

    def __init__(
        self,
        stock_repository: BranchBookStockRepository | None = None,
        closed_day_repository: BranchClosedDayRepository | None = None,
        lending_repository: LendingRepository | None = None,
        reservation_repository: ReservationRepository | None = None,
    ):
        self.stock_repository = stock_repository or BranchBookStockRepository()
        self.closed_day_repository = (
            closed_day_repository or BranchClosedDayRepository()
        )
        self.lending_repository = lending_repository or LendingRepository()
        self.reservation_repository = reservation_repository or ReservationRepository()

    def validate_registration(
        self,
        lending_input: LendingRegistrationInput,
    ) -> None:
        """
        貸出対象の自治体スコープと対応職員の所属条件を検証する。
        """
        selected_municipality = lending_input.selected_municipality
        stock = lending_input.branch_book_stock
        contact_staff = lending_input.contact_staff

        if (
            selected_municipality is not None
            and stock.branch.municipality_id != selected_municipality.id
        ):
            raise LendingMunicipalityMismatchError("branch_book_stock")
        if (
            selected_municipality is not None
            and contact_staff.branch_id is not None
            and contact_staff.branch.municipality_id != selected_municipality.id
        ):
            raise LendingMunicipalityMismatchError("contact_staff")
        if contact_staff.branch_id is None:
            raise ContactStaffBranchRequiredError
        if contact_staff.branch.municipality_id != stock.branch.municipality_id:
            raise ContactStaffMunicipalityMismatchError

    def lend(self, lending_input: LendingRegistrationInput) -> Lending:
        """
        貸出可能冊数と利用者別ルールを確認して貸出情報を作成する。
        """
        self.validate_registration(lending_input)

        with transaction.atomic():
            stock = self.stock_repository.get_for_update(
                lending_input.branch_book_stock.book,
                lending_input.branch_book_stock.branch,
            )
            if stock is None:
                raise LendingStockUnavailableError

            municipality_id = stock.branch.municipality_id
            if self.lending_repository.exists_active_book_by_customer_in_municipality(
                customer=lending_input.customer,
                book=stock.book,
                municipality_id=municipality_id,
            ):
                raise DuplicateBookLendingError

            held_reservation = (
                self.reservation_repository.get_held_by_customer_for_update(
                    stock=stock,
                    customer=lending_input.customer,
                )
            )
            active_stock_count = self.lending_repository.count_active_by_stock(stock)
            held_stock_count = self.reservation_repository.count_held_by_stock(stock)
            if active_stock_count + held_stock_count >= stock.amount and (
                held_reservation is None
            ):
                raise LendingStockUnavailableError

            active_customer_count = self.lending_repository.count_active_by_customer(
                lending_input.customer
            )
            if active_customer_count >= lending_input.customer.max_lending_count:
                raise CustomerLendingLimitExceededError

            adjusted_return_date, adjustment_reason = self._adjust_return_date(
                branch=stock.branch,
                return_date=lending_input.return_date,
            )
            lending = self.lending_repository.create(
                stock=stock,
                customer=lending_input.customer,
                contact_staff=lending_input.contact_staff,
                return_date=adjusted_return_date,
                original_return_date=lending_input.return_date,
                return_date_adjustment_reason=adjustment_reason,
            )
            if held_reservation is not None:
                self.reservation_repository.save_status(
                    held_reservation,
                    Reservation.Status.FULFILLED,
                )

            return lending

    def _adjust_return_date(
        self, *, branch: Branch, return_date: date
    ) -> tuple[date, str]:
        """
        返却予定日が支店休館日に当たる場合、次の開館日へ繰り延べる。
        """
        adjusted_date = return_date
        closed_reasons = []

        while True:
            closed_day = self.closed_day_repository.get_by_branch_and_date(
                branch=branch,
                closed_date=adjusted_date,
            )
            if closed_day is None:
                break

            if closed_day.reason:
                closed_reasons.append(closed_day.reason)
            adjusted_date += timedelta(days=1)

        return adjusted_date, "、".join(closed_reasons)

    def return_lending(
        self,
        *,
        lending_id: int,
        selected_municipality=None,
    ) -> LendingReturn:
        """
        選択中自治体内の貸出中情報を返却済みに更新する。
        """
        with transaction.atomic():
            lending = self.lending_repository.get_for_update(lending_id)
            if lending is None:
                raise LendingNotFoundError

            if (
                selected_municipality is not None
                and lending.branch_book_stock.branch.municipality_id
                != selected_municipality.id
            ):
                raise LendingNotFoundError

            if not lending.active:
                raise LendingAlreadyReturnedError

            lending.active = False
            self.lending_repository.save(lending)
            held_reservation = self._hold_next_waiting(lending.branch_book_stock)

        return LendingReturn(lending=lending, held_reservation=held_reservation)

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
