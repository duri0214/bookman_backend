from django.db import transaction
from rest_framework import serializers

from bookman.models import Author, Book, Branch, BranchBookStock, Category, Municipality
from bookman.serializers.stock import BookBranchStockSerializer


class BookSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.order_by("id")
    )
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        allow_empty=False,
        queryset=Author.objects.order_by("id"),
    )
    municipality = serializers.PrimaryKeyRelatedField(
        queryset=Municipality.objects.order_by("id"),
        write_only=True,
        required=False,
    )
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.order_by("id"),
        write_only=True,
        required=False,
    )
    amount = serializers.IntegerField(min_value=1, write_only=True, required=False)
    branch_stocks = serializers.SerializerMethodField()
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
            "municipality",
            "branch",
            "amount",
        ]
        extra_kwargs = {"isbn": {"validators": []}}

    def validate_isbn(self, value):
        """
        ISBN は前後の空白とハイフンを除いた値で保存し、形式と重複を検証する。
        """
        normalized_value = value.strip().replace("-", "")
        if not normalized_value:
            raise serializers.ValidationError("この項目は空にできません。")

        is_isbn_10 = (
            len(normalized_value) == 10
            and normalized_value[:9].isdigit()
            and (normalized_value[9].isdigit() or normalized_value[9] == "X")
        )
        is_isbn_13 = len(normalized_value) == 13 and normalized_value.isdigit()
        if not is_isbn_10 and not is_isbn_13:
            raise serializers.ValidationError(
                "ISBN-10 または ISBN-13 の形式で入力してください。"
            )

        duplicate_queryset = Book.objects.filter(isbn=normalized_value)
        if self.instance is not None:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)
        if duplicate_queryset.exists():
            raise serializers.ValidationError("このISBNは既に登録されています。")

        return normalized_value

    def validate_name(self, value):
        """
        書籍名は前後の空白を除いた値で保存し、重複を拒否する。
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("この項目は空にできません。")
        duplicate_queryset = Book.objects.filter(name=trimmed_value)
        if self.instance is not None:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)
        if duplicate_queryset.exists():
            raise serializers.ValidationError("この書籍名は既に登録されています。")
        return trimmed_value

    def validate(self, attrs):
        """
        書籍登録時は初期所蔵支店と冊数を同時に検証する。
        """
        attrs = super().validate(attrs)
        if self.instance is not None:
            return attrs

        municipality = attrs.get("municipality")
        branch = attrs.get("branch")
        errors = {}
        if municipality is None:
            errors["municipality"] = "この項目は必須です。"
        if branch is None:
            errors["branch"] = "この項目は必須です。"
        if attrs.get("amount") is None:
            errors["amount"] = "この項目は必須です。"
        if errors:
            raise serializers.ValidationError(errors)

        if (
            municipality is not None
            and branch is not None
            and branch.municipality_id != municipality.id
        ):
            raise serializers.ValidationError(
                {"branch": "指定自治体に属する支店を指定してください。"}
            )

        selected_municipality = self.context.get("municipality")
        if (
            selected_municipality is not None
            and municipality is not None
            and municipality.id != selected_municipality.id
        ):
            raise serializers.ValidationError(
                {"municipality": "選択中自治体を指定してください。"}
            )

        return attrs

    def create(self, validated_data):
        """
        書籍本体、著者関連、初期支店別所蔵数を同一トランザクションで作成する。
        """
        authors = validated_data.pop("authors")
        branch = validated_data.pop("branch")
        amount = validated_data.pop("amount")
        validated_data.pop("municipality")

        with transaction.atomic():
            book = Book.objects.create(**validated_data)
            book.authors.set(authors)
            BranchBookStock.objects.create(book=book, branch=branch, amount=amount)

        return book

    def get_total_amount(self, obj):
        """
        指定自治体内の支店別所蔵数の小計を合計して返す。
        """
        annotated_branch_amount_total = getattr(obj, "total_amount", None)
        if annotated_branch_amount_total is not None:
            return annotated_branch_amount_total

        municipality = self.context.get("municipality")
        branch_stocks = obj.branch_stocks.all()
        if municipality is not None:
            branch_stocks = branch_stocks.filter(branch__municipality=municipality)

        return sum(branch_stock.amount for branch_stock in branch_stocks)

    def get_branch_stocks(self, obj):
        """
        指定自治体内の支店別所蔵数だけを返す。
        """
        municipality = self.context.get("municipality")
        branch_stocks = obj.branch_stocks.select_related("branch").order_by(
            "branch_id",
            "id",
        )
        if municipality is not None:
            branch_stocks = branch_stocks.filter(branch__municipality=municipality)

        return BookBranchStockSerializer(branch_stocks, many=True).data
