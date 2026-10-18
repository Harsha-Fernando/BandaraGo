from django.db import migrations


def preserve_times(apps, schema_editor):
    Place = apps.get_model('attractions', 'Place')
    for place in Place.objects.using(schema_editor.connection.alias).all():
        if place.opening_hours.strip():
            continue
        opening = place.opening_time
        closing = place.closing_time
        if opening and closing:
            hours = f'{opening.strftime("%H:%M")} - {closing.strftime("%H:%M")}'
        elif opening:
            hours = f'From {opening.strftime("%H:%M")}'
        elif closing:
            hours = f'Until {closing.strftime("%H:%M")}'
        else:
            continue
        Place.objects.using(schema_editor.connection.alias).filter(pk=place.pk).update(opening_hours=hours)


class Migration(migrations.Migration):
    dependencies = [('attractions', '0004_alter_place_google_maps_query')]

    operations = [
        migrations.RunPython(preserve_times, migrations.RunPython.noop),
        migrations.RemoveField(model_name='place', name='opening_time'),
        migrations.RemoveField(model_name='place', name='closing_time'),
    ]
