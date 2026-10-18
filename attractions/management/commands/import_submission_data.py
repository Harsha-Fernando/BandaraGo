import hashlib
import json
from pathlib import Path

from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from attractions.models import Category, Place, PlaceImage


class Command(BaseCommand):
    help = 'Restore an attraction/photo package offline, skipping existing place slugs.'

    def add_arguments(self, parser):
        parser.add_argument('directory', nargs='?', default=str(settings.BASE_DIR / 'submission-data'))

    def handle(self, *args, **options):
        directory = Path(options['directory']).resolve()
        saved_files = []
        imported = skipped = 0
        try:
            manifest = json.loads((directory / 'places.json').read_text(encoding='utf-8'))
            if set(manifest) != {'version', 'categories', 'places'} or manifest['version'] != 1:
                raise ValueError('Unsupported attraction package format.')
            category_slugs = [category['slug'] for category in manifest['categories']]
            place_slugs = [record['fields']['slug'] for record in manifest['places']]
            if len(set(category_slugs)) != len(category_slugs) or len(set(place_slugs)) != len(place_slugs):
                raise ValueError('The package contains duplicate slugs.')
            allowed_fields = {field.name for field in Place._meta.concrete_fields if not field.primary_key}
            # Check every file before saving any records or copying photographs.
            for record in manifest['places']:
                if set(record['fields']) != allowed_fields:
                    raise ValueError('Place fields do not match the current application schema.')
                if not set(record['categories']) <= set(category_slugs):
                    raise ValueError('A place refers to an unknown category.')
                if record['fields']['is_published'] and (not record['categories'] or not record['images']):
                    raise ValueError('A published place must include a category and photograph.')
                for photo in record['images']:
                    relative = Path(photo['file'])
                    source = (directory / relative).resolve()
                    if (relative.is_absolute() or len(relative.parts) != 2 or relative.parts[0] != 'images'
                            or not source.is_relative_to(directory / 'images')):
                        raise ValueError('Photographs must be inside the package images directory.')
                    if hashlib.sha256(source.read_bytes()).hexdigest() != photo['sha256']:
                        raise ValueError(f'Photograph checksum mismatch: {relative.name}')
                    with Image.open(source) as image:
                        image.verify()
            with transaction.atomic():
                categories = {}
                for record in manifest['categories']:
                    if set(record) != {'name', 'slug', 'description', 'created_at'}:
                        raise ValueError('Unexpected category fields.')
                    category = Category.objects.filter(slug=record['slug']).first()
                    if category is None:
                        category = Category(**record)
                        category.full_clean()
                        category.save()
                        Category.objects.filter(pk=category.pk).update(created_at=record['created_at'])
                    categories[record['slug']] = category
                for record in manifest['places']:
                    fields = record['fields']
                    if Place.objects.filter(slug=fields['slug']).exists():
                        skipped += 1
                        continue
                    place = Place.objects.create(**fields)
                    place.categories.set(categories[slug] for slug in record['categories'])
                    for photo in record['images']:
                        if set(photo) != {'file', 'sha256', 'alt_text', 'display_order', 'is_cover', 'created_at'}:
                            raise ValueError('Unexpected photograph fields.')
                        image = PlaceImage(place=place, alt_text=photo['alt_text'],
                                           display_order=photo['display_order'], is_cover=photo['is_cover'])
                        with (directory / photo['file']).open('rb') as source:
                            image.image.save(Path(photo['file']).name, File(source), save=False)
                        saved_files.append((image.image.storage, image.image.name))
                        image.full_clean()
                        image.save()
                        PlaceImage.objects.filter(pk=image.pk).update(created_at=photo['created_at'])
                    place.validate_publication()
                    Place.objects.filter(pk=place.pk).update(
                        created_at=fields['created_at'], updated_at=fields['updated_at'])
                    imported += 1
        except (OSError, ValueError, KeyError, TypeError, ValidationError, IntegrityError) as error:
            for storage, name in saved_files:
                storage.delete(name)
            raise CommandError(f'Import failed; database changes were rolled back: {error}') from error
        self.stdout.write(self.style.SUCCESS(
            f'Imported {imported} places; skipped {skipped} existing places. Existing records were not overwritten.'))
