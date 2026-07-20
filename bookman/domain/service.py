from django.db import transaction

from bookman.domain.repository import BranchBookStockRepository, LendingRepository
from bookman.domain.valueobject import BranchBookStockTransfer, LendingReturn
from bookman.models import Book, Branch, BranchBookStock, Customer, Lending


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
        lending_repository: LendingRepository | None = None,
    ):
        self.stock_repository = stock_repository or BranchBookStockRepository()
        self.lending_repository = lending_repository or LendingRepository()

    def lend(
        self,
        *,
        branch_book_stock: BranchBookStock,
        customer: Customer,
        contact_user,
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

            if self.lending_repository.exists_active_book_by_customer(
                customer=customer,
                book=stock.book,
            ):
                raise DuplicateBookLendingError

            active_stock_count = self.lending_repository.count_active_by_stock(stock)
            if active_stock_count >= stock.amount:
                raise LendingStockUnavailableError

            active_customer_count = self.lending_repository.count_active_by_customer(
                customer
            )
            if active_customer_count >= customer.max_lending_count:
                raise CustomerLendingLimitExceededError

            return self.lending_repository.create(
                stock=stock,
                customer=customer,
                contact_user=contact_user,
                return_date=return_date,
            )

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

        return LendingReturn(lending=lending)
