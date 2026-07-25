from dataclasses import dataclass
from datetime import date

from bookman.models import (
    BranchBookStock,
    Customer,
    Lending,
    LibraryStaff,
    Municipality,
    Reservation,
)


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
class LendingReturn:
    """
    返却処理後の貸出状態。

    Attributes:
        lending: 返却済みに更新された貸出情報。
        held_reservation: 返却後に取り置きへ進んだ予約。該当予約がない場合は None。
    """

    lending: Lending
    held_reservation: Reservation | None = None
