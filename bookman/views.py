from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework import generics

from .models import Author, Book, Branch, BranchBookStock, Category
from .serializers import (
    AuthorSerializer,
    BranchBookStockSerializer,
    BookSerializer,
    BranchSerializer,
    CategorySerializer,
)


class BranchList(generics.ListCreateAPIView):
    serializer_class = BranchSerializer

    def get_queryset(self):
        return Branch.objects.order_by("id")


class BranchCreate(generics.CreateAPIView):
    serializer_class = BranchSerializer


class AuthorList(generics.ListAPIView):
    serializer_class = AuthorSerializer

    def get_queryset(self):
        return Author.objects.order_by("id")


class CategoryList(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.order_by("id")


class BookList(generics.ListAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        return (
            Book.objects.select_related("category")
            .annotate(total_amount=Coalesce(Sum("branch_stocks__amount"), 0))
            .prefetch_related("authors", "branch_stocks__branch")
            .order_by("category_id", "id")
        )


class BookCreate(generics.CreateAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        return (
            Book.objects.select_related("category")
            .annotate(total_amount=Coalesce(Sum("branch_stocks__amount"), 0))
            .prefetch_related("authors", "branch_stocks__branch")
        )


class BookDetail(generics.RetrieveAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        return (
            Book.objects.select_related("category")
            .annotate(total_amount=Coalesce(Sum("branch_stocks__amount"), 0))
            .prefetch_related("authors", "branch_stocks__branch")
        )


class BranchBookStockList(generics.ListCreateAPIView):
    serializer_class = BranchBookStockSerializer

    def get_queryset(self):
        return BranchBookStock.objects.select_related("branch", "book").order_by(
            "book_id", "branch_id", "id"
        )


class BranchBookStockDetail(generics.RetrieveUpdateAPIView):
    serializer_class = BranchBookStockSerializer

    def get_queryset(self):
        return BranchBookStock.objects.select_related("branch", "book")
