from django.urls import path, include
from . import views

urlpatterns = [
   path('api-auth/', include('rest_framework.urls')),
   path('api/branches/', views.BranchList.as_view(), name='branch_list'),
   path('api/branches/create/', views.BranchCreate.as_view(), name='branch_create'),
   path('api/books/', views.BookList.as_view(), name='book_list'),
   path('api/books/create/', views.BookCreate.as_view(), name='book_create'),
   path('api/books/<int:pk>/', views.BookDetail.as_view(), name='book_detail'),
   path('api/categories/', views.CategoryList.as_view(), name='category_list'),
]
