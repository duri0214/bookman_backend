from rest_framework import serializers

from bookman.domain.service import (
    ContactStaffBranchRequiredError,
    ContactStaffMunicipalityMismatchError,
    CustomerLendingLimitExceededError,
    DuplicateBookLendingError,
    LendingAlreadyReturnedError,
    LendingMunicipalityMismatchError,
    LendingNotFoundError,
    LendingService,
    LendingStockUnavailableError,
)
from bookman.domain.valueobject import LendingRegistrationInput
from bookman.exceptions import BusinessRuleApiError
from bookman.models import BranchBookStock, Customer, Lending, LibraryStaff
from bookman.serializers.reservation import ReservationSerializer


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

    def validate(self, attrs):
        """
        選択中自治体の所蔵と職員だけを貸出登録の対象にする。
        """
        municipality = self.context.get("municipality")
        stock = attrs.get("branch_book_stock")
        customer = attrs.get("customer")
        contact_staff = attrs.get("contact_staff")
        return_date = attrs.get("return_date")

        if (
            stock is None
            or customer is None
            or contact_staff is None
            or return_date is None
        ):
            return attrs

        try:
            LendingService().validate_registration(
                LendingRegistrationInput(
                    branch_book_stock=stock,
                    customer=customer,
                    contact_staff=contact_staff,
                    return_date=return_date,
                    selected_municipality=municipality,
                )
            )
        except LendingMunicipalityMismatchError as exc:
            field_name = str(exc)
            if field_name == "contact_staff":
                raise serializers.ValidationError(
                    {"contact_staff": "選択中自治体の職員を指定してください。"}
                ) from exc
            raise serializers.ValidationError(
                {"branch_book_stock": "選択中自治体の所蔵を指定してください。"}
            ) from exc
        except ContactStaffBranchRequiredError as exc:
            raise serializers.ValidationError(
                {"contact_staff": "対応者には所属支店が必要です。"}
            ) from exc
        except ContactStaffMunicipalityMismatchError as exc:
            raise serializers.ValidationError(
                {"contact_staff": "対象所蔵と同じ自治体の職員を指定してください。"}
            ) from exc

        return attrs

    def create(self, validated_data):
        """
        貸出登録の業務処理を実行する。
        """
        lending_input = LendingRegistrationInput(
            branch_book_stock=validated_data["branch_book_stock"],
            customer=validated_data["customer"],
            contact_staff=validated_data["contact_staff"],
            return_date=validated_data["return_date"],
            selected_municipality=self.context.get("municipality"),
        )
        try:
            return LendingService().lend(lending_input)
        except LendingMunicipalityMismatchError as exc:
            field_name = str(exc)
            if field_name == "contact_staff":
                raise serializers.ValidationError(
                    {"contact_staff": "選択中自治体の職員を指定してください。"}
                ) from exc
            raise serializers.ValidationError(
                {"branch_book_stock": "選択中自治体の所蔵を指定してください。"}
            ) from exc
        except ContactStaffBranchRequiredError as exc:
            raise serializers.ValidationError(
                {"contact_staff": "対応者には所属支店が必要です。"}
            ) from exc
        except ContactStaffMunicipalityMismatchError as exc:
            raise serializers.ValidationError(
                {"contact_staff": "対象所蔵と同じ自治体の職員を指定してください。"}
            ) from exc
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
