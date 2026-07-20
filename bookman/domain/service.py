from django.db import transaction

from bookman.domain.repository import BranchBookStockRepository
from bookman.domain.valueobject import BranchBookStockTransfer
from bookman.models import Book, Branch


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
