from dataclasses import dataclass

from bookman.models import BranchBookStock, Customer, Municipality


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
