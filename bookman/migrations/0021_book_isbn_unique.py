# Generated manually for Issue #64 on 2026-07-25

from django.db import migrations, models


def normalize_isbn_and_check_duplicates(apps, schema_editor):
    Book = apps.get_model("bookman", "Book")

    normalized_values = {}
    for book in Book.objects.order_by("id"):
        normalized_isbn = book.isbn.strip().replace("-", "")
        if normalized_isbn in normalized_values:
            first_book_id = normalized_values[normalized_isbn]
            message = (
                "Duplicate Book.isbn values must be resolved before applying "
                f"bookman.0021_book_isbn_unique: {normalized_isbn} "
                f"(book ids: {first_book_id}, {book.id})"
            )
            raise ValueError(message)
        normalized_values[normalized_isbn] = book.id
        if book.isbn != normalized_isbn:
            book.isbn = normalized_isbn
            book.save(update_fields=["isbn"])


class Migration(migrations.Migration):

    dependencies = [
        ("bookman", "0020_municipality_branch_scope"),
    ]

    operations = [
        migrations.RunPython(
            normalize_isbn_and_check_duplicates,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="book",
            name="isbn",
            field=models.CharField(
                max_length=20,
                unique=True,
                verbose_name="ISBNコード",
            ),
        ),
    ]
