import json
from datetime import time
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction

from attractions.models import Place


class Command(BaseCommand):
    help = 'Fill blank reference-place hours from the reviewed manifest, preserving existing staff-entered times.'

    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / 'fixtures' / 'verified_places.json'
        updated = 0
        with transaction.atomic():
            for record in json.loads(path.read_text()):
                if not record.get('hours_source'):
                    continue
                place = Place.objects.select_for_update().filter(slug=record['slug']).first()
                if place is None or place.opening_time is not None or place.closing_time is not None:
                    continue
                place.opening_time = time.fromisoformat(record['opening_time'])
                place.closing_time = time.fromisoformat(record['closing_time']) if record.get('closing_time') else None
                place.opening_hours_note = record['opening_hours_note']
                place.visitor_information += (
                    f"\n\nOpening hours source: {record['hours_source']}"
                    f"\nReviewed: {record['hours_reviewed_on']}"
                )
                place.save(update_fields=['opening_time', 'closing_time', 'opening_hours_note', 'visitor_information', 'updated_at'])
                updated += 1
        self.stdout.write(f'Updated hours for {updated} attraction(s). Existing times were retained.')
