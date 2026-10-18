import json
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction

from attractions.models import Place


class Command(BaseCommand):
    help = 'Fill blank weekly schedules from reviewed reference hours, preserving staff-entered schedules and notes.'

    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / 'fixtures' / 'verified_places.json'
        updated = 0
        with transaction.atomic():
            for record in json.loads(path.read_text()):
                if not record.get('hours_source') or not record.get('opening_hours'):
                    continue
                place = Place.objects.select_for_update().filter(slug=record['slug']).first()
                if place is None or place.opening_hours:
                    continue
                place.opening_hours = record['opening_hours']
                if not place.opening_hours_note:
                    place.opening_hours_note = record['opening_hours_note']
                source = (
                    f"\n\nOpening hours source: {record['hours_source']}"
                    f"\nReviewed: {record['hours_reviewed_on']}"
                )
                if source.strip() not in place.visitor_information:
                    place.visitor_information += source
                place.save(update_fields=['opening_hours', 'opening_hours_note', 'visitor_information', 'updated_at'])
                updated += 1
        self.stdout.write(f'Updated hours for {updated} attraction(s). Existing schedules were retained.')
