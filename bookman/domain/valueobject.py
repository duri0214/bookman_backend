from dataclasses import dataclass

from bookman.models import Book, Branch, BranchBookStock


@dataclass(frozen=True)
class BranchBookStockTransfer:
    """
    支店間移動後の所蔵状態。

    Attributes:
        book: 移動対象の書籍。
        from_branch: 移動元支店。
        to_branch: 移動先支店。
        amount: 移動した冊数。
        source_stock: 移動後の移動元支店別所蔵数。
        destination_stock: 移動後の移動先支店別所蔵数。
    """

    book: Book
    from_branch: Branch
    to_branch: Branch
    amount: int
    source_stock: BranchBookStock
    destination_stock: BranchBookStock
