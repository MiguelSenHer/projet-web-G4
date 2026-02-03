import django.core.files.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("browse", "0018_alter_assembly_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assembly",
            name="file",
            field=models.FileField(
                blank=True,
                null=True,
                storage=django.core.files.storage.FileSystemStorage(
<<<<<<< HEAD
                    location="/Users/miguel/projet-web-G4/src/browse/public_data/assemblies"
=======
                    location="/Users/Cherif/projetweb2526/projet-web-G4/src/browse/public_data/assemblies"
>>>>>>> 7359e580 (Added mapping tables to browse)
                ),
                upload_to="",
            ),
        ),
    ]
