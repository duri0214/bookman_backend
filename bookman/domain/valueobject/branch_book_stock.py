from dataclasses import dataclass

from bookman.models import Book, Branch, BranchBookStock, Municipality


@dataclass(frozen=True)
class BranchBookStockValidationInput:
    """
    支店別所蔵登録・更新前の検証入力。

    Attributes:
        branch: 所蔵を紐づける支店。
        book: 所蔵対象の書籍。
        selected_municipality: APIで選択中の自治体。未指定の場合は None。
        current_stock: 更新対象の既存所蔵。新規登録の場合は None。
    """

    branch: Branch
    book: Book
    selected_municipality: Municipality | None = None
    current_stock: BranchBookStock | None = None


@dataclass(frozen=True)
class BranchBookStockTransferInput:
    """
    支店間移動の入力値。

    Attributes:
        book: 移動対象の書籍。
        from_branch: 移動元支店。
        to_branch: 移動先支店。
        amount: 移動冊数。
    """

    book: Book
    from_branch: Branch
    to_branch: Branch
    amount: int


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
