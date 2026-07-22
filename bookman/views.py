from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import generics, status
from rest_framework.response import Response

from .exceptions import BusinessRuleApiError
from .models import (
    Author,
    Book,
    Branch,
    BranchBookStock,
    Category,
    Customer,
    Lending,
    LibraryStaff,
    Reservation,
)
from .serializers import (
    AuthorSerializer,
    BranchBookStockTransferSerializer,
    BranchBookStockSerializer,
    BookSerializer,
    BranchSerializer,
    CategorySerializer,
    CustomerSerializer,
    LendingReturnSerializer,
    LendingSerializer,
    LibraryStaffSerializer,
    ReservationCancelSerializer,
    ReservationExpireSerializer,
    ReservationSerializer,
)


class BranchList(generics.ListCreateAPIView):
    serializer_class = BranchSerializer

    def get_queryset(self):
        return Branch.objects.order_by("id")


class BranchCreate(generics.CreateAPIView):
    serializer_class = BranchSerializer


class CustomerList(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer

    def get_queryset(self):
        return Customer.objects.order_by("id")


class LibraryStaffList(generics.ListCreateAPIView):
    serializer_class = LibraryStaffSerializer

    def get_queryset(self):
        return LibraryStaff.objects.select_related("branch").order_by("id")


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
        return (
            BranchBookStock.objects.select_related("branch", "book")
            .annotate(
                active_lending_count=Count(
                    "lendings",
                    filter=Q(lendings__active=True),
                    distinct=True,
                ),
                held_reservation_count=Count(
                    "reservations",
                    filter=Q(reservations__status=Reservation.Status.HELD),
                    distinct=True,
                ),
            )
            .order_by("book_id", "branch_id", "id")
        )


class BranchBookStockDetail(generics.RetrieveUpdateAPIView):
    serializer_class = BranchBookStockSerializer

    def get_queryset(self):
        return BranchBookStock.objects.select_related("branch", "book").annotate(
            active_lending_count=Count(
                "lendings",
                filter=Q(lendings__active=True),
                distinct=True,
            ),
            held_reservation_count=Count(
                "reservations",
                filter=Q(reservations__status=Reservation.Status.HELD),
                distinct=True,
            ),
        )


class BranchBookStockTransfer(generics.GenericAPIView):
    serializer_class = BranchBookStockTransferSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = serializer.save()
        return Response(
            self.get_serializer(transfer).data,
            status=status.HTTP_200_OK,
        )


class LendingList(generics.ListCreateAPIView):
    serializer_class = LendingSerializer

    def get_queryset(self):
        return Lending.objects.select_related(
            "branch_book_stock__book",
            "branch_book_stock__branch",
            "customer",
            "contact_staff",
        ).order_by("-id")

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lending = serializer.save()
        except BusinessRuleApiError as exc:
            return Response(exc.to_response_data(), status=exc.status_code)

        return Response(
            self.get_serializer(lending).data,
            status=status.HTTP_201_CREATED,
        )


class LendingReturn(generics.GenericAPIView):
    serializer_class = LendingReturnSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except BusinessRuleApiError as exc:
            return Response(exc.to_response_data(), status=exc.status_code)

        return Response(
            self.get_serializer(result).data,
            status=status.HTTP_200_OK,
        )


class ReservationList(generics.ListCreateAPIView):
    serializer_class = ReservationSerializer

    def get_queryset(self):
        return Reservation.objects.select_related(
            "branch_book_stock__book",
            "branch_book_stock__branch",
            "customer",
        ).order_by("-id")

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reservation = serializer.save()
        except BusinessRuleApiError as exc:
            return Response(exc.to_response_data(), status=exc.status_code)

        return Response(
            self.get_serializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


class ReservationCancel(generics.GenericAPIView):
    serializer_class = ReservationCancelSerializer

    def post(self, request, pk):
        serializer = self.get_serializer(
            data=request.data,
            context={"reservation_id": pk},
        )
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except BusinessRuleApiError as exc:
            return Response(exc.to_response_data(), status=exc.status_code)

        return Response(
            self.get_serializer(result).data,
            status=status.HTTP_200_OK,
        )


class ReservationExpire(generics.GenericAPIView):
    serializer_class = ReservationExpireSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            self.get_serializer(result).data,
            status=status.HTTP_200_OK,
        )
