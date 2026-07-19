"""
Django REST Framework の serializer 定義。

serializer は、API レスポンスでは Django model を JSON にできる値へ変換し、
API リクエストでは JSON の入力値を検証して model に保存できる値へ戻す。
"""

from rest_framework import serializers

from bookman.domain.service import (
    BranchBookStockTransferService,
    InsufficientStockError,
    SourceStockNotFoundError,
)
from bookman.models import Author, Book, Branch, BranchBookStock, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "color"]


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "address", "phone", "remark"]


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
    book_name = serializers.CharField(source="book.name", read_only=True)

    class Meta:
        model = BranchBookStock
        fields = ["id", "branch", "branch_name", "book", "book_name", "amount"]


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
        同一支店への移動を拒否する。
        """
        if attrs["from_branch"] == attrs["to_branch"]:
            raise serializers.ValidationError(
                {"to_branch": "移動元と移動先には別の支店を指定してください。"}
            )

        return attrs

    def create(self, validated_data):
        """
        支店間移動の業務処理を実行する。
        """
        try:
            return BranchBookStockTransferService().transfer(**validated_data)
        except SourceStockNotFoundError as exc:
            raise serializers.ValidationError(
                {"from_branch": "移動元支店に対象書籍の所蔵がありません。"}
            ) from exc
        except InsufficientStockError as exc:
            raise serializers.ValidationError(
                {"amount": "移動元支店の所蔵数が不足しています。"}
            ) from exc


class BookSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.order_by("id")
    )
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Author.objects.order_by("id"),
    )
    branch_stocks = BookBranchStockSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id",
            "name",
            "category",
            "thumbnail",
            "authors",
            "lead_text",
            "total_amount",
            "branch_stocks",
            "isbn",
            "publication_date",
        ]

    def get_total_amount(self, obj):
        """
        支店別所蔵数の小計を合計し、自治体全体の所蔵数として返す。
        """
        annotated_branch_amount_total = getattr(obj, "total_amount", None)
        if annotated_branch_amount_total is not None:
            return annotated_branch_amount_total

        return sum(branch_stock.amount for branch_stock in obj.branch_stocks.all())
