from rest_framework import generics

from .models import Assignment, Author, Book, Branch, Category
from .serializers import (
    AuthorSerializer,
    AssignmentSerializer,
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
            .prefetch_related("authors", "assignments__branch")
            .order_by("category_id", "id")
        )


class BookCreate(generics.CreateAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        return Book.objects.select_related("category").prefetch_related(
            "authors", "assignments__branch"
        )


class BookDetail(generics.RetrieveAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        return Book.objects.select_related("category").prefetch_related(
            "authors", "assignments__branch"
        )


class AssignmentList(generics.ListCreateAPIView):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        return Assignment.objects.select_related("branch", "book").order_by(
            "book_id", "branch_id", "id"
        )


class AssignmentDetail(generics.RetrieveUpdateAPIView):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        return Assignment.objects.select_related("branch", "book")
