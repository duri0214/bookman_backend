from django.utils import timezone

from bookman.models import Book, Branch, BranchBookStock


class BranchBookStockRepository:
    """
    支店別所蔵数の永続化操作。
    """

    def get_for_update(self, book: Book, branch: Branch) -> BranchBookStock | None:
        """
        更新対象の支店別所蔵数を行ロック付きで取得する。
        """
        try:
            return BranchBookStock.objects.select_for_update().get(
                book=book,
                branch=branch,
            )
        except BranchBookStock.DoesNotExist:
            return None

    def get_or_create_for_update(
        self, book: Book, branch: Branch
    ) -> tuple[BranchBookStock, bool]:
        """
        更新対象の支店別所蔵数を行ロック付きで取得し、存在しない場合は作成する。
        """
        return BranchBookStock.objects.select_for_update().get_or_create(
            book=book,
            branch=branch,
            defaults={"amount": 0},
        )

    def save(self, stock: BranchBookStock) -> None:
        """
        支店別所蔵数を保存する。
        """
        stock.updated_at = timezone.localdate()
        stock.save(update_fields=["amount", "updated_at"])

    def bulk_save(self, stocks: list[BranchBookStock]) -> None:
        """
        複数の支店別所蔵数をまとめて保存する。
        """
        updated_at = timezone.localdate()
        for stock in stocks:
            stock.updated_at = updated_at

        BranchBookStock.objects.bulk_update(stocks, ["amount", "updated_at"])
