# Generated manually for Issue #25 on 2026-07-23

import django.db.models.deletion
from django.db import migrations, models


def create_default_municipality(apps, schema_editor):
    Municipality = apps.get_model("bookman", "Municipality")
    Branch = apps.get_model("bookman", "Branch")

    municipality = Municipality.objects.order_by("id").first()
    if municipality is None:
        municipality = Municipality.objects.create(name="既定自治体")

    Branch.objects.filter(municipality__isnull=True).update(municipality=municipality)


def remove_empty_default_municipality(apps, schema_editor):
    Municipality = apps.get_model("bookman", "Municipality")
    Municipality.objects.filter(name="既定自治体", branches__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("bookman", "0019_searchcondition"),
    ]

    operations = [
        migrations.CreateModel(
            name="Municipality",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=255,
                        unique=True,
                        verbose_name="自治体名",
                    ),
                ),
                (
                    "created_at",
                    models.DateField(auto_now_add=True, verbose_name="登録日"),
                ),
                (
                    "updated_at",
                    models.DateField(auto_now=True, null=True, verbose_name="更新日"),
                ),
            ],
            options={
                "db_table": "bookman_m_municipality",
            },
        ),
        migrations.AddField(
            model_name="branch",
            name="municipality",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="branches",
                to="bookman.municipality",
                verbose_name="自治体",
            ),
        ),
        migrations.RunPython(
            create_default_municipality,
            reverse_code=remove_empty_default_municipality,
        ),
        migrations.AlterField(
            model_name="branch",
            name="municipality",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="branches",
                to="bookman.municipality",
                verbose_name="自治体",
            ),
        ),
        migrations.AlterField(
            model_name="branch",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AddConstraint(
            model_name="branch",
            constraint=models.UniqueConstraint(
                fields=("municipality", "name"),
                name="bookman_branch_unique_municipality_name",
            ),
        ),
    ]
