import csv
import io
import re

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


class BookCsvImportSerializer(serializers.Serializer):
    file = serializers.FileField()
    municipality = serializers.PrimaryKeyRelatedField(
        queryset=Municipality.objects.order_by("id")
    )

    HEADER_FIELDS = {
        "カテゴリ": "category",
        "名前": "name",
        "著者": "authors",
        "あらすじ": "lead_text",
        "初期所蔵数": "amount",
        "所蔵支店": "branch",
        "ISBN": "isbn",
        "出版年月日": "publication_date",
    }
    AUTHOR_SEPARATOR_PATTERN = re.compile(r"[,、/;；\n]+")

    def create(self, validated_data):
        """
        CSVの各行を検証し、有効な行だけ書籍本体と初期支店別所蔵として登録する。
        """
        csv_rows, parse_errors = self._read_csv(validated_data["file"])
        municipality = validated_data["municipality"]
        row_results = self._build_row_results(csv_rows, municipality)

        created_count = 0
        with transaction.atomic():
            for row_result in row_results:
                if row_result["errors"]:
                    continue

                serializer = BookSerializer(
                    data=row_result["data"],
                    context={"municipality": municipality},
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
                created_count += 1

        errors = parse_errors
        for row_result in row_results:
            errors.extend(row_result["errors"])

        failed_count = len({error.get("row") for error in errors if error.get("row")})
        if parse_errors and not csv_rows:
            failed_count = 1

        return {
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors,
            "status": self._get_import_status(created_count, failed_count),
        }

    def _read_csv(self, uploaded_file):
        raw_content = uploaded_file.read()
        try:
            content = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw_content.decode("cp932")

        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames is None:
            return [], [{"field": "file", "message": "CSVヘッダーを入力してください。"}]

        missing_headers = [
            header for header in self.HEADER_FIELDS if header not in reader.fieldnames
        ]
        if missing_headers:
            joined_headers = "、".join(missing_headers)
            return [], [
                {
                    "field": "header",
                    "message": f"CSVヘッダーに {joined_headers} が必要です。",
                }
            ]

        rows = []
        for row_number, row in enumerate(reader, start=2):
            if all(not self._get_cell(row, header) for header in self.HEADER_FIELDS):
                continue
            rows.append({"row_number": row_number, "row": row})

        if not rows:
            return [], [{"field": "file", "message": "CSVデータ行を入力してください。"}]

        return rows, []

    def _build_row_results(self, csv_rows, municipality):
        categories = {category.name: category for category in Category.objects.all()}
        authors = {author.name: author for author in Author.objects.all()}
        branches = {
            branch.name: branch
            for branch in Branch.objects.select_related("municipality").all()
        }

        seen_names = set()
        seen_isbns = set()
        row_results = []
        for csv_row in csv_rows:
            row_number = csv_row["row_number"]
            row = csv_row["row"]
            payload, errors = self._build_payload(
                row,
                row_number,
                municipality,
                categories,
                authors,
                branches,
            )

            name = payload.get("name")
            if name:
                if name in seen_names:
                    errors.append(
                        self._build_error(
                            row_number,
                            "name",
                            "CSV内で同じ書籍名が重複しています。",
                        )
                    )
                seen_names.add(name)

            isbn = payload.get("isbn")
            if isbn:
                normalized_isbn = isbn.strip().replace("-", "")
                if normalized_isbn in seen_isbns:
                    errors.append(
                        self._build_error(
                            row_number,
                            "isbn",
                            "CSV内で同じISBNが重複しています。",
                        )
                    )
                seen_isbns.add(normalized_isbn)

            if not errors:
                serializer = BookSerializer(
                    data=payload,
                    context={"municipality": municipality},
                )
                if not serializer.is_valid():
                    errors.extend(
                        self._serializer_errors_to_row_errors(
                            row_number,
                            serializer.errors,
                        )
                    )

            row_results.append({"data": payload, "errors": errors})

        return row_results

    def _build_payload(
        self, row, row_number, municipality, categories, authors, branches
    ):
        errors = []
        category_name = self._get_cell(row, "カテゴリ")
        branch_name = self._get_cell(row, "所蔵支店")
        author_names = self._get_author_names(row)
        category = categories.get(category_name)
        branch = branches.get(branch_name)
        resolved_authors = [authors.get(author_name) for author_name in author_names]

        if category is None:
            errors.append(
                self._build_error(
                    row_number, "category", "指定されたカテゴリが存在しません。"
                )
            )

        if not author_names:
            errors.append(
                self._build_error(row_number, "authors", "著者を入力してください。")
            )
        missing_author_names = [
            author_name
            for author_name, author in zip(author_names, resolved_authors)
            if author is None
        ]
        if missing_author_names:
            joined_author_names = "、".join(missing_author_names)
            errors.append(
                self._build_error(
                    row_number,
                    "authors",
                    f"指定された著者が存在しません: {joined_author_names}",
                )
            )

        if branch is None:
            errors.append(
                self._build_error(
                    row_number, "branch", "指定された支店が存在しません。"
                )
            )
        elif branch.municipality_id != municipality.id:
            errors.append(
                self._build_error(
                    row_number,
                    "branch",
                    "指定自治体に属する支店を指定してください。",
                )
            )

        return (
            {
                "category": category.id if category else None,
                "name": self._get_cell(row, "名前"),
                "authors": [
                    author.id for author in resolved_authors if author is not None
                ],
                "lead_text": self._get_cell(row, "あらすじ"),
                "amount": self._get_cell(row, "初期所蔵数"),
                "branch": branch.id if branch else None,
                "municipality": municipality.id,
                "isbn": self._get_cell(row, "ISBN"),
                "publication_date": self._get_cell(row, "出版年月日"),
            },
            errors,
        )

    def _get_author_names(self, row):
        author_value = self._get_cell(row, "著者")
        return [
            author_name.strip()
            for author_name in self.AUTHOR_SEPARATOR_PATTERN.split(author_value)
            if author_name.strip()
        ]

    def _serializer_errors_to_row_errors(self, row_number, serializer_errors):
        errors = []
        for field, messages in serializer_errors.items():
            if isinstance(messages, list):
                for message in messages:
                    errors.append(self._build_error(row_number, field, str(message)))
            else:
                errors.append(self._build_error(row_number, field, str(messages)))
        return errors

    def _get_cell(self, row, header):
        return (row.get(header) or "").strip()

    def _build_error(self, row_number, field, message):
        error = {"field": field, "message": message}
        if row_number is not None:
            error["row"] = row_number
        return error

    def _get_import_status(self, created_count, failed_count):
        if created_count > 0 and failed_count == 0:
            return "success"
        if created_count > 0:
            return "partial_success"
        return "failed"
