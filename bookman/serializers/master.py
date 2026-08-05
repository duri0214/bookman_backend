import re

from django.db.models import Sum
from rest_framework import serializers

from bookman.models import (
    Author,
    Branch,
    BranchClosedDay,
    Category,
    Customer,
    LibraryStaff,
    Municipality,
    SearchCondition,
)


PHONE_NUMBER_PATTERN = re.compile(r"^\d{2,5}-\d{1,4}-\d{4}$")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "color"]

    def validate_name(self, value):
        """
        カテゴリ名は前後の空白を除いた値で保存する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        duplicate_queryset = Category.objects.filter(name=trimmed_value)
        if self.instance is not None:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)
        if duplicate_queryset.exists():
            raise serializers.ValidationError("このカテゴリ名は既に登録されています。")
        return trimmed_value

    def validate_color(self, value):
        """
        色コードは # から始まる6桁の16進数で保存する。
        """
        if not value:
            raise serializers.ValidationError("この項目は空にできません。")
        if len(value) != 7 or not value.startswith("#"):
            raise serializers.ValidationError(
                "#から始まる6桁の16進数を指定してください。"
            )

        hex_digits = value[1:]
        if not all(character in "0123456789abcdefABCDEF" for character in hex_digits):
            raise serializers.ValidationError(
                "#から始まる6桁の16進数を指定してください。"
            )

        return value.lower()


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]

    def validate_name(self, value):
        """
        著者名は前後の空白を除いた値で保存する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        return trimmed_value


class MunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipality
        fields = ["id", "name"]

    def validate_name(self, value):
        """
        自治体名は前後の空白を除いた値で保存する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        return trimmed_value


class BranchSerializer(serializers.ModelSerializer):
    municipality = serializers.PrimaryKeyRelatedField(
        queryset=Municipality.objects.order_by("id"),
        required=False,
    )
    municipality_name = serializers.CharField(
        source="municipality.name", read_only=True
    )
    book_stock_book_count = serializers.SerializerMethodField()
    book_stock_total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "municipality",
            "municipality_name",
            "name",
            "address",
            "phone",
            "remark",
            "book_stock_book_count",
            "book_stock_total_amount",
        ]
        validators = []

    def get_book_stock_book_count(self, obj):
        """
        支店に登録されている書籍種類数を返す。
        """
        annotated_count = getattr(obj, "book_stock_book_count", None)
        if annotated_count is not None:
            return annotated_count

        return obj.book_stocks.values("book").distinct().count()

    def get_book_stock_total_amount(self, obj):
        """
        支店別所蔵数の合計冊数を返す。
        """
        annotated_total = getattr(obj, "book_stock_total_amount", None)
        if annotated_total is not None:
            return annotated_total

        total_amount = obj.book_stocks.aggregate(total=Sum("amount"))["total"]
        return total_amount or 0

    def validate_name(self, value):
        """
        支店名は前後の空白を除いた値で保存する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        return trimmed_value

    def validate_address(self, value):
        """
        支店住所は前後の空白を除いた値で保存する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        return trimmed_value

    def validate_phone(self, value):
        """
        支店電話番号は前後の空白を除き、国内電話番号のハイフン区切り形式で保存する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        digit_count = sum(character.isdigit() for character in trimmed_value)
        if not PHONE_NUMBER_PATTERN.fullmatch(trimmed_value) or digit_count not in [
            10,
            11,
        ]:
            raise serializers.ValidationError(
                "電話番号は 03-3403-2591 または 090-0000-0000 の形式で入力してください。"
            )
        return trimmed_value

    def validate_remark(self, value):
        """
        支店補足情報は任意入力として、前後の空白を除いた値で保存する。
        """
        return value.strip()

    def validate(self, attrs):
        """
        選択中自治体の支店だけを登録・更新の対象にし、同一自治体内の支店名重複を拒否する。
        """
        municipality = self.context.get("municipality")
        branch_municipality = attrs.get("municipality")
        if self.instance is not None and branch_municipality is None:
            branch_municipality = self.instance.municipality

        if (
            municipality is not None
            and branch_municipality is not None
            and branch_municipality.id != municipality.id
        ):
            raise serializers.ValidationError(
                {"municipality": "選択中自治体を指定してください。"}
            )

        branch_name = attrs.get("name")
        if branch_municipality is not None and branch_name is not None:
            duplicate_queryset = Branch.objects.filter(
                municipality=branch_municipality,
                name=branch_name,
            )
            if self.instance is not None:
                duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)
            if duplicate_queryset.exists():
                raise serializers.ValidationError(
                    {"name": "この自治体には同じ支店名が既に登録されています。"}
                )

        return attrs


class BranchClosedDaySerializer(serializers.ModelSerializer):
    """
    支店休館日APIの入出力。

    支店と日付単位で休館日を登録し、理由を任意で保持する。
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = BranchClosedDay
        fields = ["id", "branch", "branch_name", "date", "reason"]

    def validate(self, attrs):
        """
        選択中自治体の支店だけを休館日登録の対象にする。
        """
        municipality = self.context.get("municipality")
        branch = attrs.get("branch")
        if self.instance is not None and branch is None:
            branch = self.instance.branch

        if (
            municipality is not None
            and branch is not None
            and branch.municipality_id != municipality.id
        ):
            raise serializers.ValidationError(
                {"branch": "選択中自治体の支店を指定してください。"}
            )

        return attrs


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "max_lending_count"]

    def validate_max_lending_count(self, value):
        """
        貸出上限冊数は1冊以上を必須にする。
        """
        if value <= 0:
            raise serializers.ValidationError("1以上の値を指定してください。")

        return value


class LibraryStaffSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=["counter", "manager", "admin"])

    class Meta:
        model = LibraryStaff
        fields = ["id", "name", "branch", "role"]

    def validate(self, attrs):
        """
        選択中自治体の支店に所属する職員だけを登録・更新の対象にする。
        """
        municipality = self.context.get("municipality")
        branch = attrs.get("branch")
        if self.instance is not None and branch is None:
            branch = self.instance.branch

        if (
            municipality is not None
            and branch is not None
            and branch.municipality_id != municipality.id
        ):
            raise serializers.ValidationError(
                {"branch": "選択中自治体の支店を指定してください。"}
            )

        return attrs


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
