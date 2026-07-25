from rest_framework import serializers

from bookman.domain.service import (
    BranchBookStockMunicipalityMismatchError,
    BranchBookStockTransferService,
    CrossMunicipalityTransferError,
    DuplicateBranchBookStockError,
    InsufficientStockError,
    SameBranchTransferError,
    SourceStockNotFoundError,
)
from bookman.domain.valueobject import (
    BranchBookStockTransferInput,
    BranchBookStockValidationInput,
)
from bookman.models import Book, Branch, BranchBookStock, Reservation


class BookBranchStockSerializer(serializers.ModelSerializer):
    """
    書籍詳細・一覧の中に埋め込む支店別所蔵数。

    書籍を起点に読むため、書籍IDは含めず支店と数量だけを返す。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = BranchBookStock
        fields = ["id", "branch", "branch_name", "amount"]


class BranchBookStockSerializer(serializers.ModelSerializer):
    """
    支店別所蔵数APIの入出力。

    POST/PATCH の入力では branch、book、amount を受け取り、
    レスポンスでは画面表示用に branch_name と book_name も返す。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    municipality = serializers.IntegerField(
        source="branch.municipality_id", read_only=True
    )
    municipality_name = serializers.CharField(
        source="branch.municipality.name", read_only=True
    )
    book_name = serializers.CharField(source="book.name", read_only=True)
    available_amount = serializers.SerializerMethodField()

    class Meta:
        model = BranchBookStock
        fields = [
            "id",
            "branch",
            "branch_name",
            "municipality",
            "municipality_name",
            "book",
            "book_name",
            "amount",
            "available_amount",
        ]
        validators = []

    def get_available_amount(self, obj):
        """
        支店別所蔵数から貸出中と取り置き中の冊数を差し引いた貸出可能冊数を返す。
        """
        active_lending_count = getattr(obj, "active_lending_count", None)
        if active_lending_count is None:
            active_lending_count = obj.lendings.filter(active=True).count()

        held_reservation_count = getattr(obj, "held_reservation_count", None)
        if held_reservation_count is None:
            held_reservation_count = obj.reservations.filter(
                status=Reservation.Status.HELD
            ).count()

        return max(obj.amount - active_lending_count - held_reservation_count, 0)

    def validate(self, attrs):
        """
        選択中自治体の支店だけを所蔵数登録・更新の対象にする。
        """
        municipality = self.context.get("municipality")

        branch = attrs.get("branch")
        book = attrs.get("book")
        if self.instance is not None:
            branch = branch or self.instance.branch
            book = book or self.instance.book

        if branch is None or book is None:
            return attrs

        try:
            BranchBookStockTransferService().validate_stock_registration(
                BranchBookStockValidationInput(
                    branch=branch,
                    book=book,
                    selected_municipality=municipality,
                    current_stock=self.instance,
                )
            )
        except BranchBookStockMunicipalityMismatchError as exc:
            raise serializers.ValidationError(
                {"branch": "選択中自治体の支店を指定してください。"}
            ) from exc
        except DuplicateBranchBookStockError as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "この支店には対象書籍の所蔵が既に登録されています。"
                    ]
                }
            ) from exc

        return attrs


class BranchBookStockTransferSerializer(serializers.Serializer):
    """
    支店間の本の移動APIの入出力。

    1リクエストで移動元の所蔵数を減らし、移動先の所蔵数を増やす。
    """

    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.order_by("id"))
    from_branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.order_by("id")
    )
    to_branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.order_by("id")
    )
    amount = serializers.IntegerField(min_value=1)
    source_stock = BranchBookStockSerializer(read_only=True)
    destination_stock = BranchBookStockSerializer(read_only=True)

    def validate(self, attrs):
        """
        同一支店への移動と自治体をまたぐ移動を拒否する。
        """
        try:
            BranchBookStockTransferService().validate_transfer_request(
                BranchBookStockTransferInput(**attrs)
            )
        except SameBranchTransferError as exc:
            raise serializers.ValidationError(
                {"to_branch": "移動元と移動先には別の支店を指定してください。"}
            ) from exc
        except CrossMunicipalityTransferError as exc:
            raise serializers.ValidationError(
                {"to_branch": "自治体が異なる支店へは移動できません。"}
            ) from exc

        return attrs

    def create(self, validated_data):
        """
        支店間移動の業務処理を実行する。
        """
        try:
            return BranchBookStockTransferService().transfer(
                BranchBookStockTransferInput(**validated_data)
            )
        except SameBranchTransferError as exc:
            raise serializers.ValidationError(
                {"to_branch": "移動元と移動先には別の支店を指定してください。"}
            ) from exc
        except CrossMunicipalityTransferError as exc:
            raise serializers.ValidationError(
                {"to_branch": "自治体が異なる支店へは移動できません。"}
            ) from exc
        except SourceStockNotFoundError as exc:
            raise serializers.ValidationError(
                {"from_branch": "移動元支店に対象書籍の所蔵がありません。"}
            ) from exc
        except InsufficientStockError as exc:
            raise serializers.ValidationError(
                {"amount": "移動元支店の所蔵数が不足しています。"}
            ) from exc
