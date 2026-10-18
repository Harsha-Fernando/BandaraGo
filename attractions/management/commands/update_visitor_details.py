import json
from datetime import time
from decimal import Decimal
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction

from attractions.models import Place


class Command(BaseCommand):
    help = 'Fill reviewed weekly hours and Google Maps fields; append practical guidance without removing existing text.'

    def handle(self, *args, **options):
        records = json.loads((Path(__file__).resolve().parents[2] / 'fixtures' / 'verified_places.json').read_text())
        updated = 0
        with transaction.atomic():
            for record in records:
                place = Place.objects.select_for_update().filter(slug=record['slug']).first()
                if place is None:
                    continue
                fields = []
                if record.get('previous_latitude') and (
                    place.latitude == Decimal(record['previous_latitude'])
                    and place.longitude == Decimal(record['previous_longitude'])
                ):
                    place.latitude = Decimal(record['latitude'])
                    place.longitude = Decimal(record['longitude'])
                    fields.extend(['latitude', 'longitude'])
                    if 'The marker uses the documented camera location' in place.description:
                        place.description = record['description']
                        fields.append('description')
                    source = f"Information: Updated map reference: {record['coordinate_source']}\nReviewed: 2026-10-18"
                    if source not in place.visitor_information:
                        place.visitor_information += '\n\n' + source
                        fields.append('visitor_information')
                for field in ['opening_hours', 'google_maps_query', 'google_maps_place_id', 'google_maps_embed_url']:
                    if not getattr(place, field) and record.get(field):
                        setattr(place, field, record[field])
                        fields.append(field)
                for field in ['opening_time', 'closing_time']:
                    value = record.get(field)
                    previous = record.get('previous_' + field)
                    current = getattr(place, field)
                    if value and (current is None or (previous and current == time.fromisoformat(previous))):
                        new_time = time.fromisoformat(value)
                        if current != new_time:
                            setattr(place, field, new_time)
                            fields.append(field)
                for text in [record.get('practical_guidance'), record.get('visitor_review_source')]:
                    if text and text not in place.visitor_information:
                        place.visitor_information += '\n\n' + text
                        fields.append('visitor_information')
                old_notes = {
                    'Opening hours not verified; confirm locally before travelling.',
                    'Closed on Mondays and public holidays.',
                    'Published park listing. Food court, aquarium and market hours can differ.',
                    'Published visitor hours (Explore Sri Lanka, April 2026).',
                    'Daily. Official listings give different closing times: 5 PM and 6 PM.',
                }
                if not place.opening_hours_note or place.opening_hours_note in old_notes:
                    note = record.get('opening_hours_note', '')
                    if place.opening_hours_note != note:
                        place.opening_hours_note = note
                        fields.append('opening_hours_note')
                if fields:
                    place.save(update_fields=list(set(fields)) + ['updated_at'])
                    updated += 1
        self.stdout.write(f'Updated visitor details for {updated} attraction(s). Existing custom schedules and map fields were retained.')
