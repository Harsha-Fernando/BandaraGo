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


class DetailTests(DiscoveryTests):
    def test_detail_uses_database_coordinates(self):
        response = self.client.get(self.place.get_absolute_url())
        self.assertContains(response, '6.714444')
        self.assertContains(response, '79.986667')
        self.assertContains(response, 'map-data')
        self.assertContains(response, 'Hours not verified')
        self.assertContains(response, 'js/leaflet/leaflet.js')

    def test_unpublished_and_missing_detail_are_404(self):
        self.assertEqual(self.client.get('/attractions/draft/').status_code, 404)
        self.assertEqual(self.client.get('/attractions/missing/').status_code, 404)

    def test_map_data_is_safe_for_script_injection(self):
        self.place.name = '</script><script>alert(1)</script>'
        self.place.save()
        response = self.client.get(self.place.get_absolute_url())
        self.assertNotContains(response, '</script><script>alert(1)</script>')
        self.assertContains(response, '\\u003C/script\\u003E')


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        cls.admin_user = get_user_model().objects.create_superuser('test-admin', 'admin@example.invalid', 'Test-password-827!')
        cls.staff = get_user_model().objects.create_user('limited-staff', password='Test-password-827!', is_staff=True)
        cls.visitor = get_user_model().objects.create_user('nonstaff', password='Test-password-827!')
        cls.category = Category.objects.create(name='Nature', slug='nature')

    def setUp(self):
        import tempfile
        from django.test import override_settings
        self.media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.settings_override.disable)

    def payload(self, **overrides):
        data = dict(name='Admin test place', slug='admin-test', short_description='Synthetic test.',
                    description='Synthetic admin test record.', latitude='6.714444', longitude='79.986667',
                    categories=[self.category.pk], is_published='on',
                    **{'images-TOTAL_FORMS': '1', 'images-INITIAL_FORMS': '0', 'images-MIN_NUM_FORMS': '0',
                       'images-MAX_NUM_FORMS': '1000', 'images-0-display_order': '0'})
        data.update(overrides)
        return data

    def upload(self, name='test.png'):
        from PIL import Image
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        buffer = BytesIO(); Image.new('RGB', (8, 8), 'green').save(buffer, format='PNG')
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    def test_permissions_and_login(self):
        url = '/admin/attractions/place/add/'
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, self.payload()).status_code, 403)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertNotEqual(self.admin_user.password, 'Test-password-827!')
        self.assertTrue(self.admin_user.check_password('Test-password-827!'))

    def test_publish_needs_category_and_image(self):
        self.client.force_login(self.admin_user)
        response = self.client.post('/admin/attractions/place/add/', self.payload(categories=[]))
        self.assertContains(response, 'Choose at least one category')
        self.assertFalse(Place.objects.exists())
        response = self.client.post('/admin/attractions/place/add/', self.payload())
        self.assertContains(response, 'Keep at least one image')
        self.assertFalse(Place.objects.exists())

    def test_publish_upload_edit_and_delete(self):
        self.client.force_login(self.admin_user)
        data = self.payload(**{'images-0-image': self.upload(), 'images-0-is_cover': 'on'})
        response = self.client.post('/admin/attractions/place/add/', data)
        self.assertEqual(response.status_code, 302)
        place = Place.objects.get(slug='admin-test')
        self.assertContains(self.client.get('/attractions/'), place.name)
        image = place.images.get()
        change_url = f'/admin/attractions/place/{place.pk}/change/'
        data = self.payload(name='Updated test place', **{'images-INITIAL_FORMS': '1', 'images-0-id': image.pk,
                                                         'images-0-place': place.pk, 'images-0-is_cover': 'on'})
        self.assertEqual(self.client.post(change_url, data).status_code, 302)
        self.assertContains(self.client.get(place.get_absolute_url()), 'Updated test place')
        data['images-0-DELETE'] = 'on'
        self.assertContains(self.client.post(change_url, data), 'Keep at least one image')
        self.assertEqual(place.images.count(), 1)
        delete_url = f'/admin/attractions/place/{place.pk}/delete/'
        self.assertContains(self.client.get(delete_url), 'Are you sure')
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 302)
        self.assertFalse(Place.objects.exists())

    def test_cover_swap_and_duplicate_covers(self):
        self.client.force_login(self.admin_user)
        place = make_place(is_published=True); place.categories.add(self.category)
        one = PlaceImage.objects.create(place=place, image='one.png', is_cover=True)
        two = PlaceImage.objects.create(place=place, image='two.png')
        data = self.payload(slug=place.slug, **{'images-TOTAL_FORMS': '2', 'images-INITIAL_FORMS': '2',
                    'images-0-id': one.pk, 'images-0-place': place.pk, 'images-1-id': two.pk,
                    'images-1-place': place.pk, 'images-1-display_order': '1', 'images-1-is_cover': 'on'})
        url = f'/admin/attractions/place/{place.pk}/change/'
        self.assertEqual(self.client.post(url, data).status_code, 302)
        one.refresh_from_db(); two.refresh_from_db()
        self.assertFalse(one.is_cover); self.assertTrue(two.is_cover)
        data['images-0-is_cover'] = 'on'
        self.assertContains(self.client.post(url, data), 'Choose at most one cover')

    def test_category_delete_cannot_break_published_place(self):
        place = make_place(is_published=True); place.categories.add(self.category)
        PlaceImage.objects.create(place=place, image='test.png')
        self.client.force_login(self.admin_user)
        url = f'/admin/attractions/category/{self.category.pk}/delete/'
        self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 403)
        self.client.post('/admin/attractions/category/', {'action': 'delete_selected', '_selected_action': [self.category.pk], 'post': 'yes'})
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_invalid_upload_and_radius_are_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.admin_user)
        data = self.payload(latitude='7.5', **{'images-0-image': SimpleUploadedFile('bad.png', b'not an image')})
        response = self.client.post('/admin/attractions/place/add/', data)
        self.assertContains(response, 'within 25 km')
        self.assertContains(response, 'Upload a valid image')
        self.assertFalse(Place.objects.exists())
