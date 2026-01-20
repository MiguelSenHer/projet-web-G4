from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("browse", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="assembly",
            name="file_name",
        ),
        migrations.AddField(
            model_name="assembly",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="assemblies/"),
        ),
    ]
