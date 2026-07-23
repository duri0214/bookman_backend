from django.db import models


class Book(models.Model):
    """
    書籍マスタ
    システムを使用するひとつの自治体が束ねる、n個の支店図書館すべてが所蔵する本。
    書籍自体は数量を持たず、支店別所蔵数は BranchBookStock.amount が持つ。
    """

    name = models.CharField("タイトル", max_length=255, unique=True)
    thumbnail = models.ImageField("サムネイル", blank=True, null=True)
    category = models.ForeignKey(
        "Category", on_delete=models.PROTECT, verbose_name="カテゴリ"
    )
    authors = models.ManyToManyField("Author", verbose_name="著者")
    branches = models.ManyToManyField(
        "Branch",
        through="BranchBookStock",
        related_name="books",
        verbose_name="所蔵支店",
    )
    lead_text = models.TextField("紹介文")
    isbn = models.CharField("ISBNコード", max_length=20)
    publication_date = models.DateField("出版年月日")
    created_at = models.DateField("登録日", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    def __str__(self):
        return str(self.name)


class BranchBookStock(models.Model):
    """
    支店と書籍の多対多関係に、支店別の所蔵数を持たせる中間テーブル。
    amount は支店別の小計で、自治体全体の所蔵数は同じ書籍に紐づく amount の合計として扱う。
    """

    branch = models.ForeignKey(
        "Branch", related_name="book_stocks", on_delete=models.CASCADE
    )
    book = models.ForeignKey(
        "Book", related_name="branch_stocks", on_delete=models.CASCADE
    )
    amount = models.PositiveSmallIntegerField()
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "book"], name="bookman_branch_book_stock_unique"
            )
        ]

    def __str__(self):
        book_name = str(self.book.name)
        branch_name = str(self.branch.name)
        return f"{book_name}({self.amount}) {branch_name}"


class LibraryStaff(models.Model):
    """
    図書館業務を担当する職員。

    Attributes:
        name: 職員名。
        branch: 所属支店。
        role: 業務上の権限種別。
        created_at: 登録日。
        updated_at: 更新日。
    """

    name = models.CharField("職員名", max_length=255, unique=True)
    branch = models.ForeignKey(
        "Branch",
        related_name="staff_members",
        on_delete=models.PROTECT,
        verbose_name="所属支店",
        null=True,
        blank=True,
    )
    role = models.CharField("権限種別", max_length=50, blank=True)
    created_at = models.DateField("登録日", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    def __str__(self):
        return str(self.name)


class SearchCondition(models.Model):
    """
    管理側画面で職員が再利用する検索条件。

    Attributes:
        target_screen: 保存条件を利用する管理側画面。
        name: 職員に表示する保存条件名。
        conditions: 検索条件のJSON。
        created_by: 保存条件を作成した職員。
        branch: 支店共有の対象支店。個人条件では作成職員の所属支店を保持する。
        share_scope: 個人、支店共有、管理者共有の共有範囲。
        owner_type: 将来の利用者向け保存条件拡張に備えた所有者種別。
        created_at: 登録日。
        updated_at: 更新日。
    """

    class ShareScope(models.TextChoices):
        """
        保存条件の共有範囲。

        Attributes:
            PERSONAL: 作成職員だけが利用する保存条件。
            BRANCH: 対象支店の職員が利用する保存条件。
            ADMIN: 管理職員が全支店向けに共有する保存条件。
        """

        PERSONAL = "personal", "個人"
        BRANCH = "branch", "支店共有"
        ADMIN = "admin", "管理者共有"

    target_screen = models.CharField("対象画面", max_length=100)
    name = models.CharField("保存条件名", max_length=255)
    conditions = models.JSONField("検索条件JSON")
    created_by = models.ForeignKey(
        "LibraryStaff",
        related_name="search_conditions",
        on_delete=models.PROTECT,
        verbose_name="作成職員",
    )
    branch = models.ForeignKey(
        "Branch",
        related_name="search_conditions",
        on_delete=models.PROTECT,
        verbose_name="対象支店",
        null=True,
        blank=True,
    )
    share_scope = models.CharField(
        "共有範囲",
        max_length=20,
        choices=ShareScope.choices,
        default=ShareScope.PERSONAL,
    )
    owner_type = models.CharField("所有者種別", max_length=20, default="staff")
    created_at = models.DateField("登録日", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["target_screen", "name", "created_by"],
                name="bookman_search_condition_unique_owner_name",
            )
        ]

    def __str__(self):
        return str(self.name)


class Lending(models.Model):
    """
    支店別所蔵を起点にした貸出情報。

    Attributes:
        return_date: 返却予定日。
        original_return_date: 休館日補正前の返却予定日。
        return_date_adjustment_reason: 返却予定日を補正した理由。
        branch_book_stock: 貸出対象の支店別所蔵。
        active: 返却前の貸出であるかどうか。
        customer: 貸出を受ける利用者。
        contact_staff: 貸出・返却を受け付けた図書館職員。
        created_at: 貸出登録日。
        updated_at: 更新日。
    """

    return_date = models.DateField("返却予定日")
    original_return_date = models.DateField(
        "補正前返却予定日",
        null=True,
        blank=True,
    )
    return_date_adjustment_reason = models.CharField(
        "返却予定日補正理由",
        max_length=255,
        blank=True,
    )
    branch_book_stock = models.ForeignKey(
        "BranchBookStock",
        related_name="lendings",
        on_delete=models.CASCADE,
        verbose_name="支店別所蔵",
    )
    active = models.BooleanField("貸出中", default=True)
    customer = models.ForeignKey(
        "Customer",
        related_name="lendings",
        on_delete=models.CASCADE,
        verbose_name="利用者",
    )
    contact_staff = models.ForeignKey(
        "LibraryStaff",
        related_name="contact",
        on_delete=models.CASCADE,
        verbose_name="対応者",
    )
    created_at = models.DateField("貸出登録日", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    def __str__(self):
        book_name = str(self.branch_book_stock.book.name)
        customer_name = str(self.customer.name)
        return f"{customer_name}: {book_name}"


class Reservation(models.Model):
    """
    支店別所蔵に対する利用者の予約と取り置き状態。

    Attributes:
        status: 予約状態。waiting は予約待ち、held は取り置き中、canceled は取消済み、expired は期限切れ、fulfilled は貸出済み。
        branch_book_stock: 予約対象の支店別所蔵。
        customer: 予約した利用者。
        hold_expires_on: 取り置き期限日。waiting の間は未設定。
        created_at: 予約登録日時。
        updated_at: 更新日。
    """

    class Status(models.TextChoices):
        """
        予約の状態管理。

        Attributes:
            WAITING: 予約待ち。
            HELD: 取り置き中。
            CANCELED: 取消済み。
            EXPIRED: 取り置き期限切れ。
            FULFILLED: 取り置き後に貸出済み。
        """

        WAITING = "waiting", "予約待ち"
        HELD = "held", "取り置き中"
        CANCELED = "canceled", "取消済み"
        EXPIRED = "expired", "期限切れ"
        FULFILLED = "fulfilled", "貸出済み"

    status = models.CharField(
        "予約状態",
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    branch_book_stock = models.ForeignKey(
        "BranchBookStock",
        related_name="reservations",
        on_delete=models.CASCADE,
        verbose_name="支店別所蔵",
    )
    customer = models.ForeignKey(
        "Customer",
        related_name="reservations",
        on_delete=models.CASCADE,
        verbose_name="利用者",
    )
    hold_expires_on = models.DateField("取り置き期限日", null=True, blank=True)
    created_at = models.DateTimeField("予約登録日時", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    def __str__(self):
        book_name = str(self.branch_book_stock.book.name)
        customer_name = str(self.customer.name)
        return f"{customer_name}: {book_name} ({self.status})"


class Customer(models.Model):
    """
    図書館を利用して本を借りる利用者。

    Attributes:
        name: 利用者名。
        phone: 電話番号。
        max_lending_count: 同時に貸出できる上限冊数。
        created_at: 登録日。
        updated_at: 更新日。
    """

    name = models.CharField("利用者名", max_length=255, unique=True)
    phone = models.CharField("電話番号", max_length=20, blank=True)
    max_lending_count = models.PositiveSmallIntegerField("貸出上限冊数", default=5)
    created_at = models.DateField("登録日", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    def __str__(self):
        return str(self.name)


class Branch(models.Model):
    """
    図書館支店マスタ
    """

    name = models.CharField(max_length=255, unique=True)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    remark = models.CharField(max_length=255)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True, null=True)

    class Meta:
        db_table = "bookman_m_branch"

    def __str__(self):
        return str(self.name)


class BranchClosedDay(models.Model):
    """
    支店ごとの日付単位の休館日。

    Attributes:
        branch: 休館日を設定する支店。
        date: 休館日。
        reason: 休館理由。祝日、年末年始、蔵書点検など職員が任意で入力する。
        created_at: 登録日。
        updated_at: 更新日。
    """

    branch = models.ForeignKey(
        "Branch",
        related_name="closed_days",
        on_delete=models.CASCADE,
        verbose_name="支店",
    )
    date = models.DateField("休館日")
    reason = models.CharField("休館理由", max_length=255, blank=True)
    created_at = models.DateField("登録日", auto_now_add=True)
    updated_at = models.DateField("更新日", auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "date"], name="bookman_branch_closed_day_unique"
            )
        ]

    def __str__(self):
        branch_name = str(self.branch.name)
        return f"{branch_name}: {self.date}"


class Category(models.Model):
    name = models.CharField("カテゴリ名", max_length=100, unique=True)
    color = models.CharField("色(16進数)", max_length=7, default="#000000")

    class Meta:
        db_table = "bookman_m_category"

    def __str__(self):
        return str(self.name)


class Author(models.Model):
    name = models.CharField("著者名", max_length=255, unique=True)

    def __str__(self):
        return str(self.name)
