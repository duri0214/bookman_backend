from django.urls import path, include
from . import views

urlpatterns = [
    path("api-auth/", include("rest_framework.urls")),
    path("api/branches/", views.BranchList.as_view(), name="branch_list"),
    path(
        "api/branch-closed-days/",
        views.BranchClosedDayList.as_view(),
        name="branch_closed_day_list",
    ),
    path(
        "api/branch-closed-days/<int:pk>/",
        views.BranchClosedDayDetail.as_view(),
        name="branch_closed_day_detail",
    ),
    path("api/customers/", views.CustomerList.as_view(), name="customer_list"),
    path("api/staff/", views.LibraryStaffList.as_view(), name="library_staff_list"),
    path(
        "api/staff/<int:pk>/",
        views.LibraryStaffDetail.as_view(),
        name="library_staff_detail",
    ),
    path(
        "api/search-conditions/",
        views.SearchConditionList.as_view(),
        name="search_condition_list",
    ),
    path(
        "api/search-conditions/<int:pk>/",
        views.SearchConditionDetail.as_view(),
        name="search_condition_detail",
    ),
    path(
        "api/search-conditions/permissions/",
        views.SearchConditionPermissionContext.as_view(),
        name="search_condition_permission_context",
    ),
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
