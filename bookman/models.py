from django.contrib.auth.models import User
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


class Lending(models.Model):
    """
    支店別所蔵を起点にした貸出情報。
    貸出日と created_at は同じになり、返却が終わると active が False になる。
    """

    return_date = models.DateField()
    branch_book_stock = models.ForeignKey(
        "BranchBookStock", related_name="lendings", on_delete=models.CASCADE
    )
    active = models.BooleanField(default=True)  # pyright: ignore[reportArgumentType]
    customer_user = models.ForeignKey(
        User, related_name="customer", on_delete=models.CASCADE
    )
    contact_user = models.ForeignKey(
        User, related_name="contact", on_delete=models.CASCADE
    )
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True, null=True)


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
