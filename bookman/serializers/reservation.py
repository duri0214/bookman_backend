from rest_framework import serializers

from bookman.domain.service import (
    DuplicateBookReservationError,
    DuplicateReservationError,
    ReservationMunicipalityMismatchError,
    ReservationNotCancelableError,
    ReservationNotFoundError,
    ReservationService,
    ReservationStockAvailableError,
)
from bookman.domain.valueobject import ReservationRegistrationInput
from bookman.exceptions import BusinessRuleApiError
from bookman.models import BranchBookStock, Customer, Reservation


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

    def validate(self, attrs):
        """
        選択中自治体の所蔵だけを予約登録の対象にする。
        """
        municipality = self.context.get("municipality")
        stock = attrs.get("branch_book_stock")
        customer = attrs.get("customer")

        if stock is None or customer is None:
            return attrs

        try:
            ReservationService().validate_registration(
                ReservationRegistrationInput(
                    branch_book_stock=stock,
                    customer=customer,
                    selected_municipality=municipality,
                )
            )
        except ReservationMunicipalityMismatchError as exc:
            raise serializers.ValidationError(
                {"branch_book_stock": "選択中自治体の所蔵を指定してください。"}
            ) from exc

        return attrs

    def create(self, validated_data):
        """
        予約登録の業務処理を実行する。
        """
        reservation_input = ReservationRegistrationInput(
            branch_book_stock=validated_data["branch_book_stock"],
            customer=validated_data["customer"],
            selected_municipality=self.context.get("municipality"),
        )
        try:
            return ReservationService().reserve(reservation_input)
        except ReservationMunicipalityMismatchError as exc:
            raise serializers.ValidationError(
                {"branch_book_stock": "選択中自治体の所蔵を指定してください。"}
            ) from exc
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
