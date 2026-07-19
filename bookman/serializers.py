"""
Django REST Framework の serializer 定義。

serializer は、API レスポンスでは Django model を JSON にできる値へ変換し、
API リクエストでは JSON の入力値を検証して model に保存できる値へ戻す。
"""

from rest_framework import serializers

from bookman.models import Assignment, Author, Book, Branch, Category


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


class BookAssignmentSerializer(serializers.ModelSerializer):
    """
    書籍詳細・一覧の中に埋め込む支店別所蔵数。

    書籍を起点に読むため、書籍IDは含めず支店と数量だけを返す。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Assignment
        fields = ["id", "branch", "branch_name", "amount"]


class AssignmentSerializer(serializers.ModelSerializer):
    """
    支店別所蔵数APIの入出力。

    POST/PATCH の入力では branch、book、amount を受け取り、
    レスポンスでは画面表示用に branch_name と book_name も返す。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    book_name = serializers.CharField(source="book.name", read_only=True)

    class Meta:
        model = Assignment
        fields = ["id", "branch", "branch_name", "book", "book_name", "amount"]


class BookSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.order_by("id")
    )
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Author.objects.order_by("id"),
    )
    assignments = BookAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        fields = [
            "id",
            "name",
            "category",
            "thumbnail",
            "authors",
            "lead_text",
            "amount",
            "assignments",
            "isbn",
            "publication_date",
        ]
