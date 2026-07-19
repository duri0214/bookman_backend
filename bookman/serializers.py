from rest_framework import serializers

from bookman.models import Author, Book, Branch, Category


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


class BookSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.order_by("id")
    )
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Author.objects.order_by("id"),
    )

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
            "isbn",
            "publication_date",
        ]
