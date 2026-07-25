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


class DuplicateBranchBookStockError(BranchBookStockTransferError):
    """
    同じ支店と書籍の所蔵が既に登録されている場合の例外。
    """


class BranchBookStockMunicipalityMismatchError(BranchBookStockTransferError):
    """
    選択中自治体に属さない支店別所蔵を扱おうとした場合の例外。
    """


class SameBranchTransferError(BranchBookStockTransferError):
    """
    同一支店へ所蔵を移動しようとした場合の例外。
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


class LendingMunicipalityMismatchError(LendingRuleError):
    """
    選択中自治体に属さない所蔵または職員で貸出登録しようとした場合の例外。
    """


class ContactStaffBranchRequiredError(LendingRuleError):
    """
    貸出対応職員に所属支店がない場合の例外。
    """


class ContactStaffMunicipalityMismatchError(LendingRuleError):
    """
    貸出対象所蔵と対応職員の自治体が一致しない場合の例外。
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


class ReservationMunicipalityMismatchError(ReservationRuleError):
    """
    選択中自治体に属さない所蔵へ予約登録しようとした場合の例外。
    """


class ReservationNotFoundError(ReservationRuleError):
    """
    取消対象の予約情報が存在しない場合の例外。
    """


class ReservationNotCancelableError(ReservationRuleError):
    """
    取消対象の予約が取り消し可能な状態ではない場合の例外。
    """
