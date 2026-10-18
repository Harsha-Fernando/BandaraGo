import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from attractions.models import Category, Place


class Command(BaseCommand):
    help = 'Export attraction data and local photographs only; no accounts or sessions.'

    def add_arguments(self, parser):
        parser.add_argument('directory', nargs='?', default=str(settings.BASE_DIR / 'submission-data'))

    def handle(self, *args, **options):
        destination = Path(options['directory']).resolve()
        if destination.exists():
            raise CommandError('Destination already exists. Choose a new directory to retain the previous export.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with TemporaryDirectory(prefix='bandarago-export-', dir=destination.parent) as temporary:
                package = Path(temporary) / 'package'
                (package / 'images').mkdir(parents=True)
                categories = list(Category.objects.order_by('slug').values(
                    'name', 'slug', 'description', 'created_at'))
                places = []
                for place in Place.objects.with_details().order_by('slug'):
                    fields = {field.name: place.serializable_value(field.name)
                              for field in Place._meta.concrete_fields if not field.primary_key}
                    images = []
                    for photo in place.images.all():
                        with photo.image.open('rb') as source:
                            content = source.read()
                        digest = hashlib.sha256(content).hexdigest()
                        filename = digest + Path(photo.image.name).suffix.lower()
                        image_path = package / 'images' / filename
                        image_path.write_bytes(content)
                        with Image.open(image_path) as image:
                            image.verify()
                        images.append({
                            'file': 'images/' + filename, 'sha256': digest,
                            'alt_text': photo.alt_text, 'display_order': photo.display_order,
                            'is_cover': photo.is_cover, 'created_at': photo.created_at,
                        })
                    places.append({'fields': fields,
                                   'categories': sorted(category.slug for category in place.categories.all()),
                                   'images': images})
                manifest = {'version': 1, 'categories': categories, 'places': places}
                (package / 'places.json').write_text(
                    json.dumps(manifest, default=str, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8')
                package.rename(destination)
        except (OSError, ValueError) as error:
            raise CommandError(f'Export failed; no complete package was written: {error}') from error
        count = sum(len(place['images']) for place in places)
        self.stdout.write(self.style.SUCCESS(
            f'Exported {len(places)} places, {len(categories)} categories and {count} photographs to {destination}.'))
