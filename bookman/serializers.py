"""
Django REST Framework の serializer 定義。

serializer は、API レスポンスでは Django model を JSON にできる値へ変換し、
API リクエストでは JSON の入力値を検証して model に保存できる値へ戻す。
"""

from rest_framework import serializers

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
