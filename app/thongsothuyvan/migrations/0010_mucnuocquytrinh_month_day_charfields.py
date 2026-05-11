from django.db import migrations


def convert_postgres_date_columns_to_month_day(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'thongsothuyvan_mucnuocquytrinh'
                      AND column_name = 'ngay_bat_dau'
                      AND data_type = 'date'
                ) THEN
                    ALTER TABLE thongsothuyvan_mucnuocquytrinh
                    ALTER COLUMN ngay_bat_dau TYPE varchar(5)
                    USING to_char(ngay_bat_dau, 'DD/MM');
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'thongsothuyvan_mucnuocquytrinh'
                      AND column_name = 'ngay_ket_thuc'
                      AND data_type = 'date'
                ) THEN
                    ALTER TABLE thongsothuyvan_mucnuocquytrinh
                    ALTER COLUMN ngay_ket_thuc TYPE varchar(5)
                    USING to_char(ngay_ket_thuc, 'DD/MM');
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0009_mucnuocquytrinh"),
    ]

    operations = [
        migrations.RunPython(
            convert_postgres_date_columns_to_month_day,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
