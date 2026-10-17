import json
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from attractions.models import Category, Place, PlaceImage


class Command(BaseCommand):
    help = 'Import the reviewed ten-place reference dataset as drafts; never overwrite existing places.'

    def add_arguments(self, parser):
        parser.add_argument('--download-images', action='store_true', help='Download attributed Commons photos (internet required).')

    def handle(self, *args, **options):
        call_command('seed_categories', stdout=self.stdout)
        path = Path(__file__).resolve().parents[2] / 'fixtures' / 'verified_places.json'
        records = json.loads(path.read_text())
        for record in records:
            if Place.objects.filter(slug=record['slug']).exists():
                self.stdout.write(f"Skipped existing: {record['name']}")
                continue
            photo = record['photo']
            image_bytes = None
            if options['download_images']:
                if urlparse(photo['url']).hostname not in {'upload.wikimedia.org', 'thumb.wikimedia.org'}:
                    raise CommandError('Photo host must be Wikimedia.')
                try:
                    request = Request(photo['url'], headers={'User-Agent': 'BandaraGoAcademicProject/1.0'})
                    with urlopen(request, timeout=30) as response:
                        image_bytes = response.read(10 * 1024 * 1024 + 1)
                    if len(image_bytes) > 10 * 1024 * 1024:
                        raise ValueError('Photo exceeds 10 MB.')
                    Image.open(BytesIO(image_bytes)).verify()
                except Exception as error:
                    raise CommandError(f"Could not download {record['name']}: {error}") from error
            information = '\n\n'.join([
                record['visitor_information'],
                f"Information: {record['source_url']}\nCoordinates: {record['coordinate_source']}\nSource review: {record['verified_on']}",
                f"Photo: {photo['author']} · {photo['license']}\n{photo['source_url']}\n{photo['license_url']}\nCommons image; CSS crops display. No other changes.",
            ])
            with transaction.atomic():
                place = Place.objects.create(**{key: record[key] for key in [
                    'name', 'slug', 'latitude', 'longitude', 'short_description', 'description', 'address',
                ]}, visitor_information=information,
                    opening_hours_note=record.get('opening_hours_note', 'Opening hours not verified; confirm locally before travelling.'))
                place.categories.set(Category.objects.filter(slug__in=record['categories']))
                if image_bytes:
                    image = PlaceImage(place=place, alt_text=photo['alt_text'], is_cover=True)
                    image.image.save(f"{place.slug}.jpg", ContentFile(image_bytes), save=True)
            self.stdout.write(self.style.SUCCESS(f"Imported draft: {place.name}"))
        self.stdout.write('Review drafts and publish using the admin. Existing records were left unchanged.')
