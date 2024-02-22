from rest_framework import serializers
from bookman.models import Branch, Book, Category, Author


class BranchListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        exclude = ('created_at', 'updated_at')


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = '__all__'


class AuthorSerializer(serializers.ModelSerializer):

    class Meta:
        model = Author
        fields = '__all__'


class BookListSerializer(serializers.ModelSerializer):
    """
    本一覧
    """
    category = CategorySerializer(read_only=True)
    authors = AuthorSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        exclude = ('amount', 'isbn', 'created_at', 'updated_at')


class BookDetailSerializer(serializers.ModelSerializer):
    """
    本
    """
    category = CategorySerializer(read_only=True)
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Book
        fields = '__all__'
        
