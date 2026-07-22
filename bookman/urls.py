from django.urls import path, include
from . import views

urlpatterns = [
    path("api-auth/", include("rest_framework.urls")),
    path("api/branches/", views.BranchList.as_view(), name="branch_list"),
    path("api/branches/create/", views.BranchCreate.as_view(), name="branch_create"),
    path("api/customers/", views.CustomerList.as_view(), name="customer_list"),
    path("api/staff/", views.LibraryStaffList.as_view(), name="library_staff_list"),
    path("api/books/", views.BookList.as_view(), name="book_list"),
    path("api/books/create/", views.BookCreate.as_view(), name="book_create"),
    path("api/books/<int:pk>/", views.BookDetail.as_view(), name="book_detail"),
    path(
        "api/branch-book-stocks/",
        views.BranchBookStockList.as_view(),
        name="branch_book_stock_list",
    ),
    path(
        "api/branch-book-stocks/<int:pk>/",
        views.BranchBookStockDetail.as_view(),
        name="branch_book_stock_detail",
    ),
    path(
        "api/branch-book-stocks/transfer/",
        views.BranchBookStockTransfer.as_view(),
        name="branch_book_stock_transfer",
    ),
    path("api/lendings/", views.LendingList.as_view(), name="lending_list"),
    path(
        "api/lendings/return/",
        views.LendingReturn.as_view(),
        name="lending_return",
    ),
    path(
        "api/reservations/",
        views.ReservationList.as_view(),
        name="reservation_list",
    ),
    path(
        "api/reservations/<int:pk>/cancel/",
        views.ReservationCancel.as_view(),
        name="reservation_cancel",
    ),
    path(
        "api/reservations/expire/",
        views.ReservationExpire.as_view(),
        name="reservation_expire",
    ),
    path("api/authors/", views.AuthorList.as_view(), name="author_list"),
    path("api/categories/", views.CategoryList.as_view(), name="category_list"),
]
