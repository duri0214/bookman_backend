from rest_framework import generics
from .models import Book, Category, Branch, Author
from .serializers import CategorySerializer, BookSerializer, BranchSerializer, AuthorSerializer


class BranchList(generics.ListAPIView):
    queryset = Branch.objects.all().order_by('id')
    serializer_class = BranchSerializer


class BranchCreate(generics.CreateAPIView):
    serializer_class = BranchSerializer


class AuthorList(generics.ListAPIView):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer


class CategoryList(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class BookList(generics.ListAPIView):
    queryset = Book.objects.all().order_by('category')
    serializer_class = BookSerializer


class BookCreate(generics.CreateAPIView):
    serializer_class = BookSerializer


class BookDetail(generics.RetrieveAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
