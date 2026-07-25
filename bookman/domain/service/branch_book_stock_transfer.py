from django.db import transaction

from bookman.domain.repository import BranchBookStockRepository
from bookman.domain.service.errors import (
    BranchBookStockMunicipalityMismatchError,
    CrossMunicipalityTransferError,
    DuplicateBranchBookStockError,
    InsufficientStockError,
    SameBranchTransferError,
    SourceStockNotFoundError,
)
from bookman.domain.valueobject import (
    BranchBookStockTransfer,
    BranchBookStockTransferInput,
    BranchBookStockValidationInput,
)


class BranchBookStockTransferService:
    """
    支店別所蔵の登録前検証と支店間移動の業務処理。
    """

    def __init__(self, repository: BranchBookStockRepository | None = None):
        self.repository = repository or BranchBookStockRepository()

    def validate_stock_registration(
        self,
        stock_input: BranchBookStockValidationInput,
    ) -> None:
        """
        支店別所蔵の自治体スコープと支店・書籍の重複を検証する。
        """
        if (
            stock_input.selected_municipality is not None
            and stock_input.branch.municipality_id
            != stock_input.selected_municipality.id
        ):
            raise BranchBookStockMunicipalityMismatchError

        if self.repository.exists_by_branch_and_book(
            branch=stock_input.branch,
            book=stock_input.book,
            exclude_stock=stock_input.current_stock,
        ):
            raise DuplicateBranchBookStockError

    def validate_transfer_request(
        self,
        transfer_input: BranchBookStockTransferInput,
    ) -> None:
        """
        支店間移動の移動先と自治体境界を検証する。
        """
        if transfer_input.from_branch == transfer_input.to_branch:
            raise SameBranchTransferError
        if (
            transfer_input.from_branch.municipality_id
            != transfer_input.to_branch.municipality_id
        ):
            raise CrossMunicipalityTransferError

    def transfer(
        self,
        transfer_input: BranchBookStockTransferInput,
    ) -> BranchBookStockTransfer:
        """
        移動元の所蔵数を減らし、移動先の所蔵数を増やす。
        """
        self.validate_transfer_request(transfer_input)

        with transaction.atomic():
            source_stock = self.repository.get_for_update(
                transfer_input.book,
                transfer_input.from_branch,
            )
            if source_stock is None:
                raise SourceStockNotFoundError

            if source_stock.amount < transfer_input.amount:
                raise InsufficientStockError

            destination_stock, created = self.repository.get_or_create_for_update(
                transfer_input.book,
                transfer_input.to_branch,
            )

            source_stock.amount -= transfer_input.amount
            destination_stock.amount += transfer_input.amount

            if created:
                self.repository.save(source_stock)
                self.repository.save(destination_stock)
            else:
                self.repository.bulk_save([source_stock, destination_stock])

        return BranchBookStockTransfer(
            book=transfer_input.book,
            from_branch=transfer_input.from_branch,
            to_branch=transfer_input.to_branch,
            amount=transfer_input.amount,
            source_stock=source_stock,
            destination_stock=destination_stock,
        )
