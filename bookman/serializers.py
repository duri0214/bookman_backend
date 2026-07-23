"""
Django REST Framework の serializer 定義。

serializer は、API レスポンスでは Django model を JSON にできる値へ変換し、
API リクエストでは JSON の入力値を検証して model に保存できる値へ戻す。
"""

from rest_framework import serializers

from bookman.exceptions import BusinessRuleApiError
from bookman.domain.service import (
    BranchBookStockTransferService,
    CustomerLendingLimitExceededError,
    DuplicateBookLendingError,
    DuplicateBookReservationError,
    DuplicateReservationError,
    InsufficientStockError,
    LendingAlreadyReturnedError,
    LendingNotFoundError,
    LendingService,
    LendingStockUnavailableError,
    ReservationNotCancelableError,
    ReservationNotFoundError,
    ReservationService,
    ReservationStockAvailableError,
    SourceStockNotFoundError,
)

from bookman.models import (
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


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "color"]


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "address", "phone", "remark"]


class BranchClosedDaySerializer(serializers.ModelSerializer):
    """
    支店休館日APIの入出力。

    支店と日付単位で休館日を登録し、理由を任意で保持する。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = BranchClosedDay
        fields = ["id", "branch", "branch_name", "date", "reason"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "max_lending_count"]


class LibraryStaffSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=["counter", "manager", "admin"])

    class Meta:
        model = LibraryStaff
        fields = ["id", "name", "branch", "role"]


class SearchConditionSerializer(serializers.ModelSerializer):
    """
    管理側の保存済み検索条件APIの入出力。

    入力では職員、対象画面、条件JSON、共有範囲を受け取り、
    レスポンスでは職員名、支店名、操作可否も返す。
    """

    created_by_name = serializers.CharField(source="created_by.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    can_update = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = SearchCondition
        fields = [
            "id",
            "target_screen",
            "name",
            "conditions",
            "created_by",
            "created_by_name",
            "branch",
            "branch_name",
            "share_scope",
            "owner_type",
            "can_update",
            "can_delete",
        ]
        read_only_fields = ["owner_type"]

    def validate(self, attrs):
        """
        保存条件の共有範囲と職員権限の整合性を検証する。
        """
        created_by = attrs.get("created_by") or getattr(
            self.instance,
            "created_by",
            None,
        )
        request_staff = self.context.get("staff") or created_by
        share_scope = attrs.get(
            "share_scope",
            getattr(self.instance, "share_scope", SearchCondition.ShareScope.PERSONAL),
        )
        branch = attrs.get("branch", getattr(self.instance, "branch", None))

        if (
            self.instance is not None
            and "created_by" in attrs
            and attrs["created_by"] != self.instance.created_by
        ):
            raise serializers.ValidationError(
                {"created_by": "保存条件の作成職員は変更できません。"}
            )

        if created_by is None or request_staff is None:
            return attrs

        if share_scope == SearchCondition.ShareScope.PERSONAL and branch is None:
            attrs["branch"] = created_by.branch

        if share_scope == SearchCondition.ShareScope.BRANCH:
            if request_staff.role not in ["manager", "admin"]:
                raise serializers.ValidationError(
                    {
                        "share_scope": "支店共有の保存条件は manager または admin のみ作成できます。"
                    }
                )
            if branch is None:
                branch = created_by.branch
                attrs["branch"] = branch
            if branch is None:
                raise serializers.ValidationError(
                    {"branch": "支店共有の保存条件には対象支店が必要です。"}
                )

        if (
            share_scope == SearchCondition.ShareScope.ADMIN
            and request_staff.role
            not in (
                "manager",
                "admin",
            )
        ):
            raise serializers.ValidationError(
                {
                    "share_scope": "管理者共有の保存条件は manager または admin のみ作成できます。"
                }
            )

        return attrs

    def get_can_update(self, obj):
        """
        リクエスト職員が保存条件を更新できるかどうかを返す。
        """
        staff = self.context.get("staff")
        return can_manage_search_condition(staff, obj)

    def get_can_delete(self, obj):
        """
        リクエスト職員が保存条件を削除できるかどうかを返す。
        """
        staff = self.context.get("staff")
        return can_manage_search_condition(staff, obj)


def can_manage_search_condition(staff, condition):
    """
    職員ロールと所有関係から保存条件を変更できるか判定する。
    """
    if staff is None:
        return False
    if staff.role == "admin":
        return True
    if staff.role == "manager":
        return condition.share_scope != SearchCondition.ShareScope.ADMIN or (
            condition.created_by_id == staff.id
        )
    return condition.created_by_id == staff.id


class BookBranchStockSerializer(serializers.ModelSerializer):
    """
    書籍詳細・一覧の中に埋め込む支店別所蔵数。

    書籍を起点に読むため、書籍IDは含めず支店と数量だけを返す。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = BranchBookStock
        fields = ["id", "branch", "branch_name", "amount"]


class BranchBookStockSerializer(serializers.ModelSerializer):
    """
    支店別所蔵数APIの入出力。

    POST/PATCH の入力では branch、book、amount を受け取り、
    レスポンスでは画面表示用に branch_name と book_name も返す。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    book_name = serializers.CharField(source="book.name", read_only=True)
    available_amount = serializers.SerializerMethodField()

    class Meta:
        model = BranchBookStock
        fields = [
            "id",
            "branch",
            "branch_name",
            "book",
            "book_name",
            "amount",
            "available_amount",
        ]

    def get_available_amount(self, obj):
        """
        支店別所蔵数から貸出中と取り置き中の冊数を差し引いた貸出可能冊数を返す。
        """
        active_lending_count = getattr(obj, "active_lending_count", None)
        if active_lending_count is None:
            active_lending_count = obj.lendings.filter(active=True).count()

        held_reservation_count = getattr(obj, "held_reservation_count", None)
        if held_reservation_count is None:
            held_reservation_count = obj.reservations.filter(
                status=Reservation.Status.HELD
            ).count()

        return max(obj.amount - active_lending_count - held_reservation_count, 0)


class BranchBookStockTransferSerializer(serializers.Serializer):
    """
    支店間の本の移動APIの入出力。

    1リクエストで移動元の所蔵数を減らし、移動先の所蔵数を増やす。
    """

    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.order_by("id"))
    from_branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.order_by("id")
    )
    to_branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.order_by("id")
    )
    amount = serializers.IntegerField(min_value=1)
    source_stock = BranchBookStockSerializer(read_only=True)
    destination_stock = BranchBookStockSerializer(read_only=True)

    def validate(self, attrs):
        """
        同一支店への移動を拒否する。
        """
        if attrs["from_branch"] == attrs["to_branch"]:
            raise serializers.ValidationError(
                {"to_branch": "移動元と移動先には別の支店を指定してください。"}
            )

        return attrs

    def create(self, validated_data):
        """
        支店間移動の業務処理を実行する。
        """
        try:
            return BranchBookStockTransferService().transfer(**validated_data)
        except SourceStockNotFoundError as exc:
            raise serializers.ValidationError(
                {"from_branch": "移動元支店に対象書籍の所蔵がありません。"}
            ) from exc
        except InsufficientStockError as exc:
            raise serializers.ValidationError(
                {"amount": "移動元支店の所蔵数が不足しています。"}
            ) from exc


class LendingSerializer(serializers.ModelSerializer):
    """
    貸出APIの入出力。

    入力では支店別所蔵、利用者、対応職員、返却予定日を受け取り、
    レスポンスでは貸出中フラグと表示用名称も返す。
    """

    branch_book_stock = serializers.PrimaryKeyRelatedField(
        queryset=BranchBookStock.objects.order_by("id")
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.order_by("id")
    )
    contact_staff = serializers.PrimaryKeyRelatedField(
        queryset=LibraryStaff.objects.order_by("id")
    )
    book_name = serializers.CharField(
        source="branch_book_stock.book.name", read_only=True
    )
    branch_name = serializers.CharField(
        source="branch_book_stock.branch.name", read_only=True
    )
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    contact_staff_name = serializers.CharField(
        source="contact_staff.name", read_only=True
    )
    return_date_adjusted = serializers.SerializerMethodField()

    class Meta:
        model = Lending
        fields = [
            "id",
            "branch_book_stock",
            "book_name",
            "branch_name",
            "customer",
            "customer_name",
            "contact_staff",
            "contact_staff_name",
            "return_date",
            "original_return_date",
            "return_date_adjusted",
            "return_date_adjustment_reason",
            "active",
        ]
        read_only_fields = [
            "active",
            "original_return_date",
            "return_date_adjusted",
            "return_date_adjustment_reason",
        ]

    def get_return_date_adjusted(self, obj):
        """
        返却予定日が休館日により補正されたかどうかを返す。
        """
        return (
            obj.original_return_date is not None
            and obj.original_return_date != obj.return_date
        )

    def create(self, validated_data):
        """
        貸出登録の業務処理を実行する。
        """
        try:
            return LendingService().lend(**validated_data)
        except DuplicateBookLendingError as exc:
            raise BusinessRuleApiError(
                code="duplicate_book_lending",
                message="同じ利用者は同じ本を2冊以上借りられません。",
            ) from exc
        except LendingStockUnavailableError as exc:
            raise BusinessRuleApiError(
                code="lending_stock_unavailable",
                message="対象の本は貸出可能冊数が残っていません。",
            ) from exc
        except CustomerLendingLimitExceededError as exc:
            raise BusinessRuleApiError(
                code="customer_lending_limit_exceeded",
                message="利用者の貸出上限冊数に達しています。",
            ) from exc


class ReservationSerializer(serializers.ModelSerializer):
    """
    予約APIの入出力。

    入力では支店別所蔵と利用者を受け取り、レスポンスでは予約状態と画面表示用名称も返す。
    """

    branch_book_stock = serializers.PrimaryKeyRelatedField(
        queryset=BranchBookStock.objects.order_by("id")
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.order_by("id")
    )
    book_name = serializers.CharField(
        source="branch_book_stock.book.name", read_only=True
    )
    branch_name = serializers.CharField(
        source="branch_book_stock.branch.name", read_only=True
    )
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "branch_book_stock",
            "book_name",
            "branch_name",
            "customer",
            "customer_name",
            "status",
            "hold_expires_on",
            "created_at",
        ]
        read_only_fields = ["status", "hold_expires_on", "created_at"]

    def create(self, validated_data):
        """
        予約登録の業務処理を実行する。
        """
        try:
            return ReservationService().reserve(**validated_data)
        except ReservationStockAvailableError as exc:
            raise BusinessRuleApiError(
                code="reservation_stock_available",
                message="対象の本は貸出可能冊数が残っているため予約できません。",
            ) from exc
        except DuplicateReservationError as exc:
            raise BusinessRuleApiError(
                code="duplicate_reservation",
                message="同じ利用者は同じ支店別所蔵へ重複して予約できません。",
            ) from exc
        except DuplicateBookReservationError as exc:
            raise BusinessRuleApiError(
                code="duplicate_book_reservation",
                message="同じ本を貸出中の利用者は予約できません。",
            ) from exc


class ReservationCancelSerializer(serializers.Serializer):
    """
    予約取消APIの入出力。

    URLで指定された予約IDを取り消し、取消後の予約情報を返す。
    """

    canceled_reservation = ReservationSerializer(read_only=True)

    def create(self, validated_data):
        """
        予約取消の業務処理を実行する。
        """
        try:
            return ReservationService().cancel(
                reservation_id=self.context["reservation_id"]
            )
        except ReservationNotFoundError as exc:
            raise BusinessRuleApiError(
                code="reservation_not_found",
                message="取消対象の予約情報が見つかりません。",
            ) from exc
        except ReservationNotCancelableError as exc:
            raise BusinessRuleApiError(
                code="reservation_not_cancelable",
                message="取消対象の予約は取り消しできない状態です。",
            ) from exc

    def to_representation(self, instance):
        """
        取消後の予約情報を canceled_reservation として返す。
        """
        return {"canceled_reservation": ReservationSerializer(instance).data}


class ReservationExpireSerializer(serializers.Serializer):
    """
    取り置き期限切れ処理APIの入出力。

    期限切れになった取り置きを expired へ更新し、更新件数と対象予約を返す。
    """

    expired_count = serializers.IntegerField(read_only=True)
    expired_reservations = ReservationSerializer(read_only=True, many=True)

    def create(self, validated_data):
        """
        取り置き期限切れ処理を実行する。
        """
        expired_reservations = ReservationService().expire_due_holds()
        return {
            "expired_count": len(expired_reservations),
            "expired_reservations": expired_reservations,
        }


class LendingReturnSerializer(serializers.Serializer):
    """
    返却APIの入出力。

    貸出IDを受け取り、返却後の貸出情報を返す。
    """

    lending = serializers.IntegerField(write_only=True, min_value=1)
    returned_lending = LendingSerializer(read_only=True)
    held_reservation = ReservationSerializer(read_only=True)

    def create(self, validated_data):
        """
        返却の業務処理を実行する。
        """
        try:
            return LendingService().return_lending(lending_id=validated_data["lending"])
        except LendingNotFoundError as exc:
            raise BusinessRuleApiError(
                code="lending_not_found",
                message="返却対象の貸出情報が見つかりません。",
            ) from exc
        except LendingAlreadyReturnedError as exc:
            raise BusinessRuleApiError(
                code="lending_already_returned",
                message="返却対象の貸出情報はすでに返却済みです。",
            ) from exc

    def to_representation(self, instance):
        """
        返却後の貸出情報と、取り置きへ進んだ予約があれば held_reservation として返す。
        """
        held_reservation = None
        if instance.held_reservation is not None:
            held_reservation = ReservationSerializer(instance.held_reservation).data

        return {
            "returned_lending": LendingSerializer(instance.lending).data,
            "held_reservation": held_reservation,
        }


class BookSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.order_by("id")
    )
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Author.objects.order_by("id"),
    )
    branch_stocks = BookBranchStockSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id",
            "name",
            "category",
            "thumbnail",
            "authors",
            "lead_text",
            "total_amount",
            "branch_stocks",
            "isbn",
            "publication_date",
        ]

    def get_total_amount(self, obj):
        """
        支店別所蔵数の小計を合計し、自治体全体の所蔵数として返す。
        """
        annotated_branch_amount_total = getattr(obj, "total_amount", None)
        if annotated_branch_amount_total is not None:
            return annotated_branch_amount_total

        return sum(branch_stock.amount for branch_stock in obj.branch_stocks.all())
