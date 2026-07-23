from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response

from .exceptions import BusinessRuleApiError
from .models import (
    Author,
    Book,
    Branch,
    BranchBookStock,
    BranchClosedDay,
    Category,
    Customer,
    Lending,
    LibraryStaff,
    Reservation,
    SearchCondition,
)
from .serializers import (
    AuthorSerializer,
    BranchBookStockTransferSerializer,
    BranchBookStockSerializer,
    BranchClosedDaySerializer,
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
    SearchConditionSerializer,
    can_manage_search_condition,
)


class BranchList(generics.ListCreateAPIView):
    serializer_class = BranchSerializer

    def get_queryset(self):
        return Branch.objects.order_by("id")


class BranchCreate(generics.CreateAPIView):
    serializer_class = BranchSerializer


class BranchClosedDayList(generics.ListCreateAPIView):
    serializer_class = BranchClosedDaySerializer

    def get_queryset(self):
        queryset = BranchClosedDay.objects.select_related("branch").order_by(
            "branch_id",
            "date",
            "id",
        )
        branch_id = self.request.query_params.get("branch")
        if branch_id is not None:
            queryset = queryset.filter(branch_id=branch_id)

        return queryset


class BranchClosedDayDetail(generics.DestroyAPIView):
    serializer_class = BranchClosedDaySerializer

    def get_queryset(self):
        return BranchClosedDay.objects.select_related("branch")


class CustomerList(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer

    def get_queryset(self):
        return Customer.objects.order_by("id")


class LibraryStaffList(generics.ListCreateAPIView):
    serializer_class = LibraryStaffSerializer

    def get_queryset(self):
        return LibraryStaff.objects.select_related("branch").order_by("id")


class LibraryStaffDetail(generics.RetrieveUpdateAPIView):
    serializer_class = LibraryStaffSerializer

    def get_queryset(self):
        return LibraryStaff.objects.select_related("branch")


class SearchConditionAccessMixin:
    """
    リクエスト職員を起点に保存済み検索条件の参照・操作範囲を決める mixin。
    """

    def get_staff(self):
        """
        query parameter または request body の staff ID から職員を取得する。
        """
        staff_id = self.request.query_params.get("staff") or self.request.data.get(
            "staff"
        )
        if staff_id is None and self.request.method == "POST":
            staff_id = self.request.data.get("created_by")
        if staff_id is None:
            return None

        return LibraryStaff.objects.select_related("branch").filter(id=staff_id).first()

    def get_serializer_context(self):
        """
        serializer に操作可否判定用の職員コンテキストを渡す。
        """
        context = super().get_serializer_context()
        context["staff"] = self.get_staff()
        return context

    def get_visible_queryset(self):
        """
        職員ロールで参照可能な保存済み検索条件だけを返す。
        """
        staff = self.get_staff()
        queryset = SearchCondition.objects.select_related(
            "created_by",
            "branch",
        ).order_by("target_screen", "name", "id")

        target_screen = self.request.query_params.get("target_screen")
        if target_screen:
            queryset = queryset.filter(target_screen=target_screen)

        if staff is None:
            return queryset.none()

        if staff.role in ["manager", "admin"]:
            return queryset

        return queryset.filter(
            Q(created_by=staff)
            | Q(
                share_scope=SearchCondition.ShareScope.BRANCH,
                branch=staff.branch,
            )
            | Q(share_scope=SearchCondition.ShareScope.ADMIN)
        )


class SearchConditionList(SearchConditionAccessMixin, generics.ListCreateAPIView):
    serializer_class = SearchConditionSerializer

    def get_queryset(self):
        return self.get_visible_queryset()


class SearchConditionDetail(
    SearchConditionAccessMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = SearchConditionSerializer

    def get_queryset(self):
        return self.get_visible_queryset()

    def perform_update(self, serializer):
        staff = self.get_staff()
        if not can_manage_search_condition(staff, self.get_object()):
            raise PermissionDenied("この保存条件を更新する権限がありません。")
        serializer.save()

    def perform_destroy(self, instance):
        staff = self.get_staff()
        if not can_manage_search_condition(staff, instance):
            raise PermissionDenied("この保存条件を削除する権限がありません。")
        instance.delete()


class SearchConditionPermissionContext(APIView):
    """
    管理側画面が disabled 表示に使う職員別の操作可否情報を返す。
    """

    def get(self, request):
        staff_id = request.query_params.get("staff")
        staff = (
            LibraryStaff.objects.select_related("branch").filter(id=staff_id).first()
        )
        if staff is None:
            return Response(
                {
                    "staff": None,
                    "role": "",
                    "branch": None,
                    "can_create_personal": False,
                    "can_create_branch": False,
                    "can_create_admin": False,
                    "record_scope": "none",
                    "disabled_reason": "職員を指定してください。",
                }
            )

        is_manager = staff.role in ["manager", "admin"]
        branch = None
        if staff.branch is not None:
            branch = {"id": staff.branch.id, "name": staff.branch.name}

        disabled_reason = ""
        if not is_manager:
            disabled_reason = (
                "支店共有と管理者共有の作成には manager または admin 権限が必要です。"
            )

        return Response(
            {
                "staff": staff.id,
                "role": staff.role,
                "branch": branch,
                "can_create_personal": True,
                "can_create_branch": is_manager,
                "can_create_admin": is_manager,
                "record_scope": "all" if is_manager else "own_branch",
                "disabled_reason": disabled_reason,
            }
        )


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
