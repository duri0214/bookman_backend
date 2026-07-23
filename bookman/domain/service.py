from datetime import date, timedelta

from django.db import transaction

from bookman.domain.repository import (
    BranchBookStockRepository,
    BranchClosedDayRepository,
    LendingRepository,
    ReservationRepository,
)
from bookman.domain.valueobject import BranchBookStockTransfer, LendingReturn
from bookman.models import (
    Book,
    Branch,
    BranchBookStock,
    Customer,
    Lending,
    LibraryStaff,
    Reservation,
)


class BranchBookStockTransferError(Exception):
    """
    支店間移動が業務ルール上実行できない場合の例外。
    """


class SourceStockNotFoundError(BranchBookStockTransferError):
    """
    移動元支店に対象書籍の所蔵がない場合の例外。
    """


class InsufficientStockError(BranchBookStockTransferError):
    """
    移動元支店の所蔵数が移動冊数に満たない場合の例外。
    """


class CrossMunicipalityTransferError(BranchBookStockTransferError):
    """
    自治体が異なる支店間で移動しようとした場合の例外。
    """


class LendingRuleError(Exception):
    """
    貸出・返却が業務ルール上実行できない場合の例外。
    """


class DuplicateBookLendingError(LendingRuleError):
    """
    同じ利用者が同じ書籍を貸出中の場合の例外。
    """


class LendingStockUnavailableError(LendingRuleError):
    """
    貸出対象の支店別所蔵に貸出可能冊数が残っていない場合の例外。
    """


class CustomerLendingLimitExceededError(LendingRuleError):
    """
    利用者の貸出上限冊数に達している場合の例外。
    """


class LendingNotFoundError(LendingRuleError):
    """
    返却対象の貸出情報が存在しない場合の例外。
    """


class LendingAlreadyReturnedError(LendingRuleError):
    """
    返却対象の貸出情報がすでに返却済みの場合の例外。
    """


class ReservationRuleError(Exception):
    """
    予約が業務ルール上実行できない場合の例外。
    """


class ReservationStockAvailableError(ReservationRuleError):
    """
    予約対象の支店別所蔵に貸出可能冊数が残っている場合の例外。
    """


class DuplicateReservationError(ReservationRuleError):
    """
    同じ利用者が同じ支店別所蔵へ未完了の予約を持つ場合の例外。
    """


class DuplicateBookReservationError(ReservationRuleError):
    """
    同じ利用者が同じ書籍を貸出中の場合の予約例外。
    """


class ReservationNotFoundError(ReservationRuleError):
    """
    取消対象の予約情報が存在しない場合の例外。
    """


class ReservationNotCancelableError(ReservationRuleError):
    """
    取消対象の予約が取り消し可能な状態ではない場合の例外。
    """


class BranchBookStockTransferService:
    """
    支店間で本を移動する業務処理。
    """

    def __init__(self, repository: BranchBookStockRepository | None = None):
        self.repository = repository or BranchBookStockRepository()

    def transfer(
        self,
        *,
        book: Book,
        from_branch: Branch,
        to_branch: Branch,
        amount: int,
    ) -> BranchBookStockTransfer:
        """
        移動元の所蔵数を減らし、移動先の所蔵数を増やす。
        """
        if from_branch.municipality_id != to_branch.municipality_id:
            raise CrossMunicipalityTransferError

        with transaction.atomic():
            source_stock = self.repository.get_for_update(book, from_branch)
            if source_stock is None:
                raise SourceStockNotFoundError

            if source_stock.amount < amount:
                raise InsufficientStockError

            destination_stock, created = self.repository.get_or_create_for_update(
                book,
                to_branch,
            )

            source_stock.amount -= amount
            destination_stock.amount += amount

            if created:
                self.repository.save(source_stock)
                self.repository.save(destination_stock)
            else:
                self.repository.bulk_save([source_stock, destination_stock])

        return BranchBookStockTransfer(
            book=book,
            from_branch=from_branch,
            to_branch=to_branch,
            amount=amount,
            source_stock=source_stock,
            destination_stock=destination_stock,
        )


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

    def lend(
        self,
        *,
        branch_book_stock: BranchBookStock,
        customer: Customer,
        contact_staff: LibraryStaff,
        return_date,
    ) -> Lending:
        """
        貸出可能冊数と利用者別ルールを確認して貸出情報を作成する。
        """
        with transaction.atomic():
            stock = self.stock_repository.get_for_update(
                branch_book_stock.book,
                branch_book_stock.branch,
            )
            if stock is None:
                raise LendingStockUnavailableError

            municipality_id = stock.branch.municipality_id
            if self.lending_repository.exists_active_book_by_customer_in_municipality(
                customer=customer,
                book=stock.book,
                municipality_id=municipality_id,
            ):
                raise DuplicateBookLendingError

            held_reservation = (
                self.reservation_repository.get_held_by_customer_for_update(
                    stock=stock,
                    customer=customer,
                )
            )
            active_stock_count = self.lending_repository.count_active_by_stock(stock)
            held_stock_count = self.reservation_repository.count_held_by_stock(stock)
            if active_stock_count + held_stock_count >= stock.amount and (
                held_reservation is None
            ):
                raise LendingStockUnavailableError

            active_customer_count = self.lending_repository.count_active_by_customer(
                customer
            )
            if active_customer_count >= customer.max_lending_count:
                raise CustomerLendingLimitExceededError

            adjusted_return_date, adjustment_reason = self._adjust_return_date(
                branch=stock.branch,
                return_date=return_date,
            )
            lending = self.lending_repository.create(
                stock=stock,
                customer=customer,
                contact_staff=contact_staff,
                return_date=adjusted_return_date,
                original_return_date=return_date,
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

    def return_lending(self, *, lending_id: int) -> LendingReturn:
        """
        貸出中の貸出情報を返却済みに更新する。
        """
        with transaction.atomic():
            lending = self.lending_repository.get_for_update(lending_id)
            if lending is None:
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

    def reserve(
        self,
        *,
        branch_book_stock: BranchBookStock,
        customer: Customer,
    ) -> Reservation:
        """
        貸出可能冊数がない支店別所蔵へ予約待ちを登録する。
        """
        with transaction.atomic():
            stock = self.stock_repository.get_for_update(
                branch_book_stock.book,
                branch_book_stock.branch,
            )
            if stock is None:
                raise LendingStockUnavailableError

            if self.reservation_repository.exists_open_by_customer_and_stock(
                stock=stock,
                customer=customer,
            ):
                raise DuplicateReservationError

            municipality_id = stock.branch.municipality_id
            if self.lending_repository.exists_active_book_by_customer_in_municipality(
                customer=customer,
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
                customer=customer,
            )

    def cancel(self, *, reservation_id: int) -> Reservation:
        """
        予約待ちまたは取り置き中の予約を取り消す。
        """
        with transaction.atomic():
            reservation = self.reservation_repository.get_for_update(reservation_id)
            if reservation is None:
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

    def expire_due_holds(self) -> list[Reservation]:
        """
        期限切れの取り置きを expired にし、同じ支店別所蔵の次の予約を取り置きへ進める。
        """
        expired_reservations = []
        stocks_to_promote = []

        with transaction.atomic():
            due_holds = self.reservation_repository.list_due_holds_for_update()
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
