from io import StringIO
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from .distance import BANDARAGAMA_LATITUDE, BANDARAGAMA_LONGITUDE, distance_from_bandaragama
from .models import Category, Place, PlaceImage


def make_place(**overrides):
    values = dict(name='Test attraction', slug='test-attraction', short_description='Synthetic test record.',
                  description='Synthetic test data, not visitor information.', latitude='6.714444', longitude='79.986667')
    values.update(overrides)
    return Place.objects.create(**values)


class ModelTests(TestCase):
    def test_distance_center_and_known_separation(self):
        self.assertAlmostEqual(distance_from_bandaragama(BANDARAGAMA_LATITUDE, BANDARAGAMA_LONGITUDE), 0)
        self.assertAlmostEqual(distance_from_bandaragama(BANDARAGAMA_LATITUDE + 0.1, BANDARAGAMA_LONGITUDE), 11.1195, places=3)

    def test_radius_and_coordinate_validation_on_save(self):
        for lat, lon in [('91', '80'), ('6', '181'), ('7.5', '80'), ('-91', '80')]:
            with self.subTest(latitude=lat, longitude=lon), self.assertRaises(ValidationError):
                make_place(latitude=lat, longitude=lon)

    def test_database_coordinate_constraint(self):
        place = make_place()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Place.objects.filter(pk=place.pk).update(latitude=100)

    def test_category_seeding_is_idempotent(self):
        for _ in range(2):
            call_command('seed_categories', stdout=StringIO())
        self.assertEqual(Category.objects.count(), 5)

    def test_category_uniqueness_and_links(self):
        category = Category.objects.create(name='Nature', slug='nature')
        place = make_place()
        place.categories.add(category, category)
        self.assertEqual(place.categories.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name='Nature', slug='other')

    def test_publication_requires_related_objects(self):
        place = make_place(is_published=True)
        with self.assertRaises(ValidationError):
            place.validate_publication()
        self.assertFalse(Place.objects.published().exists())
        place.categories.add(Category.objects.create(name='Nature', slug='nature'))
        with self.assertRaises(ValidationError):
            place.validate_publication()
        PlaceImage.objects.create(place=place, image='synthetic-test.png')
        place.validate_publication()
        self.assertEqual(Place.objects.published().count(), 1)

    def test_only_one_cover_per_place(self):
        place = make_place()
        image = PlaceImage.objects.create(place=place, image='test.png', is_cover=True)
        self.assertEqual(place.cover_image, image)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlaceImage.objects.create(place=place, image='other.png', is_cover=True)

    def test_place_deletion_cascades_images(self):
        place = make_place()
        PlaceImage.objects.create(place=place, image='test.png')
        place.delete()
        self.assertEqual(PlaceImage.objects.count(), 0)

    def test_slug_uniqueness(self):
        make_place()
        with self.assertRaises(ValidationError):
            make_place()


class DiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.nature = Category.objects.create(name='Nature', slug='nature')
        cls.heritage = Category.objects.create(name='Heritage', slug='heritage')
        cls.place = make_place(is_published=True)
        cls.place.categories.add(cls.nature)
        PlaceImage.objects.create(place=cls.place, image='test.png')
        make_place(name='Hidden draft', slug='draft')

    def test_home_and_listing_only_show_published(self):
        for url in ['/', '/attractions/']:
            response = self.client.get(url)
            self.assertContains(response, self.place.name)
            self.assertNotContains(response, 'Hidden draft')
            self.assertContains(response, '0.0 km from Bandaragama')

    def test_filter_and_clear(self):
        response = self.client.get('/attractions/', {'category': 'nature'})
        self.assertContains(response, self.place.name)
        self.assertContains(response, 'Clear filter')
        self.assertNotContains(self.client.get('/attractions/', {'category': 'heritage'}), self.place.name)

    def test_empty_and_invalid_category(self):
        for value in ['heritage', 'missing', "' OR 1=1 --"]:
            response = self.client.get('/attractions/', {'category': value})
            self.assertContains(response, 'No attractions match this category')
        Place.objects.all().delete()
        self.assertContains(self.client.get('/'), 'No attractions are available yet')

    def test_prefetched_relations_bound_queries(self):
        with self.assertNumQueries(3):
            places = list(Place.objects.published().with_details())
            for place in places:
                list(place.categories.all())
                place.cover_image
