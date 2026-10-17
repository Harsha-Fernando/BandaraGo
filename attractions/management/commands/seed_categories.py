from django.core.management.base import BaseCommand
from django.utils.text import slugify
from attractions.models import Category


class Command(BaseCommand):
    help = 'Create the five approved tourism categories without duplicating them.'

    def handle(self, *args, **options):
        for name in ['Religious', 'Heritage', 'Nature', 'Cultural', 'Leisure']:
            Category.objects.get_or_create(name=name, defaults={'slug': slugify(name)})
        self.stdout.write(self.style.SUCCESS('Five tourism categories are available.'))
