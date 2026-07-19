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
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Assignment
        fields = ["id", "branch", "branch_name", "amount"]


class AssignmentSerializer(serializers.ModelSerializer):
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
