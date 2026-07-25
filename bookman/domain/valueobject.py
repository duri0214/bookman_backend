from dataclasses import dataclass
from datetime import date

from bookman.models import (
    Book,
    Branch,
    BranchBookStock,
    Customer,
    Lending,
    LibraryStaff,
    Municipality,
    Reservation,
)


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
class LendingRegistrationInput:
    """
    貸出登録の入力値。

    Attributes:
        branch_book_stock: 貸出対象の支店別所蔵。
        customer: 貸出を受ける利用者。
        contact_staff: 貸出対応職員。
        return_date: 返却予定日。
        selected_municipality: APIで選択中の自治体。未指定の場合は None。
    """

    branch_book_stock: BranchBookStock
    customer: Customer
    contact_staff: LibraryStaff
    return_date: date
    selected_municipality: Municipality | None = None


@dataclass(frozen=True)
class ReservationRegistrationInput:
    """
    予約登録の入力値。

    Attributes:
        branch_book_stock: 予約対象の支店別所蔵。
        customer: 予約する利用者。
        selected_municipality: APIで選択中の自治体。未指定の場合は None。
    """

    branch_book_stock: BranchBookStock
    customer: Customer
    selected_municipality: Municipality | None = None


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


@dataclass(frozen=True)
class LendingReturn:
    """
    返却処理後の貸出状態。

    Attributes:
        lending: 返却済みに更新された貸出情報。
        held_reservation: 返却後に取り置きへ進んだ予約。該当予約がない場合は None。
    """

    lending: Lending
    held_reservation: Reservation | None = None
