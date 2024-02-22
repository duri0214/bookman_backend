from rest_framework import generics
from .models import Book, Category, Branch
from .serializers import CategorySerializer, BookListSerializer, BookDetailSerializer, BranchListSerializer


class BranchList(generics.ListAPIView):
    queryset = Branch.objects.all().order_by('id')
    serializer_class = BranchListSerializer


class CategoryList(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class BookList(generics.ListAPIView):
    queryset = Book.objects.all().order_by('category')
    serializer_class = BookListSerializer


class BookDetail(generics.RetrieveAPIView):
    queryset = Book.objects.all()
    serializer_class = BookDetailSerializer
