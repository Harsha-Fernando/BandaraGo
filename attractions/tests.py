from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

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
            self.assertContains(response, '0.0 km straight-line from Bandaragama')

    def test_public_pages_use_local_bootstrap_assets(self):
        from django.contrib.staticfiles import finders

        assets = ['vendor/bootstrap/css/bootstrap.min.css', 'css/style.css',
                  'vendor/bootstrap/js/bootstrap.bundle.min.js', 'icons/bootstrap-icons.svg']
        for asset in assets:
            self.assertIsNotNone(finders.find(asset))
        for url in ['/', '/attractions/', self.place.get_absolute_url(), '/planner/',
                    '/planner/clear/confirm/']:
            response = self.client.get(url)
            for asset in assets[:3]:
                self.assertContains(response, f'/static/{asset}')

    def test_cards_offer_csrf_protected_add_and_plain_text_brand(self):
        for url in ['/', '/attractions/']:
            response = self.client.get(url)
            self.assertContains(response, f'action="/planner/add/{self.place.pk}/"')
            self.assertContains(response, 'csrfmiddlewaretoken')
            self.assertContains(response, 'Add to Plan')
            self.assertNotContains(response, '#bank')
            self.assertNotContains(response, 'Photo credits')

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


class DetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Nature', slug='nature')
        cls.place = make_place(is_published=True)
        cls.place.categories.add(category)
        PlaceImage.objects.create(place=cls.place, image='test.png')
        make_place(slug='draft')

    def test_detail_uses_database_coordinates(self):
        response = self.client.get(self.place.get_absolute_url())
        self.assertContains(response, '6.714444')
        self.assertContains(response, '79.986667')
        self.assertContains(response, 'map-data')
        self.assertContains(response, 'Hours not published')
        from django.contrib.staticfiles import finders
        for asset in ['vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css']:
            self.assertContains(response, f'/static/{asset}')
            self.assertIsNotNone(finders.find(asset))
        for image in ['marker-icon.png', 'marker-icon-2x.png', 'marker-shadow.png']:
            self.assertIsNotNone(finders.find(f'vendor/leaflet/images/{image}'))

    def test_source_records_are_hidden_and_visitor_guidance_is_preserved(self):
        self.place.visitor_information = (
            'Wear suitable footwear.\n\n'
            'Information: https://example.invalid/source\nSource review: 2026-10-18\n\n'
            'Photo: Test author · CC BY 2.0\nhttps://example.invalid/photo'
        )
        self.place.save()
        response = self.client.get(self.place.get_absolute_url())
        self.assertEqual(response.context['visitor_guidance'], 'Wear suitable footwear.')
        self.assertNotContains(response, 'Sources &amp; image credits')
        self.assertNotContains(response, 'Test author')
        self.assertNotContains(response, 'https://example.invalid/source')
        self.assertNotContains(response, 'https://example.invalid/photo')
        self.place.refresh_from_db()
        self.assertIn('Test author', self.place.visitor_information)

    def test_hours_and_map_links_use_database_values(self):
        self.place.opening_hours = 'Monday–Sunday: 6:00 AM–9:00 PM'
        self.place.opening_hours_note = 'Closed on public holidays.'
        self.place.save()
        response = self.client.get(self.place.get_absolute_url())
        self.assertContains(response, 'Monday–Sunday: 6:00 AM–9:00 PM')
        self.assertContains(response, 'Closed on public holidays.')
        from urllib.parse import parse_qs, urlsplit
        parameters = parse_qs(urlsplit(self.place.map_url).query)
        self.assertIn(self.place.name, parameters['query'][0])
        self.assertNotContains(response, 'Get Directions')
        self.assertNotContains(response, '/maps/dir/')
        self.assertNotContains(response, 'View on OpenStreetMap')
        self.assertNotContains(response, 'use the coordinates')
        self.place.opening_hours = ''
        self.place.save()
        self.assertContains(self.client.get(self.place.get_absolute_url()), 'Hours not published')

    def test_sources_after_guidance_need_no_blank_line(self):
        original = ('Wear suitable footwear.\n  Information: https://example.invalid/source\n'
                    'Photo: Example author\nhttps://example.invalid/photo')
        self.place.visitor_information = original
        self.place.save()
        response = self.client.get(self.place.get_absolute_url())
        self.assertEqual(response.context['visitor_guidance'], 'Wear suitable footwear.')
        self.assertNotContains(response, 'example.invalid')
        self.place.visitor_information = original.replace('Wear suitable footwear.',
            'Confirm current admission and access arrangements before visiting.')
        self.place.save()
        response = self.client.get(self.place.get_absolute_url())
        self.assertNotContains(response, 'Good to know')
        self.assertNotContains(response, 'example.invalid')
        self.place.refresh_from_db()
        self.assertIn('Example author', self.place.visitor_information)

    def test_weekly_hours_take_priority_and_google_embed_is_optional(self):
        self.place.opening_hours = 'Monday: Closed\nTuesday–Sunday: 8:30 AM–4:15 PM'
        self.place.google_maps_embed_url = 'https://www.google.com/maps/embed?pb=!1m18!verified'
        self.place.google_maps_query = 'Specific museum, Ratmalana, Sri Lanka'
        self.place.google_maps_place_id = 'verified-place-id'
        self.place.save()
        response = self.client.get(self.place.get_absolute_url())
        self.assertContains(response, 'Monday: Closed')
        self.assertContains(response, 'Tuesday–Sunday: 8:30 AM–4:15 PM')
        self.assertContains(response, '<iframe')
        self.assertContains(response, self.place.google_maps_embed_url)
        self.assertNotContains(response, 'vendor/leaflet/leaflet.js')
        self.assertNotContains(response, 'Hours not published')
        self.assertIn('query_place_id=verified-place-id', self.place.map_url)
        for invalid in ['https://evil.example/maps/embed?pb=x', 'javascript:alert(1)',
                        'https://www.google.com.evil.example/maps/embed?pb=x',
                        'https://www.google.com/maps/embed/v1/place?key=x']:
            self.place.google_maps_embed_url = invalid
            with self.assertRaises(ValidationError):
                self.place.full_clean()

    def test_detail_sends_referrer_policy_required_for_osm_tiles(self):
        response = self.client.get(self.place.get_absolute_url())
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')

    def test_unpublished_and_missing_detail_are_404(self):
        self.assertEqual(self.client.get('/attractions/draft/').status_code, 404)
        self.assertEqual(self.client.get('/attractions/missing/').status_code, 404)

    def test_gallery_uses_real_photos_with_cover_first(self):
        cover = PlaceImage.objects.create(place=self.place, image='cover.png', is_cover=True, display_order=5)
        response = self.client.get(self.place.get_absolute_url())
        self.assertEqual(response.context['photos'][0], cover)
        self.assertEqual(len(response.context['photos']), 2)
        self.assertContains(response, cover.image.url)
        cover.delete()
        response = self.client.get(self.place.get_absolute_url())
        self.assertEqual(len(response.context['photos']), 1)
        self.assertNotContains(response, cover.image.url)

    def test_more_places_excludes_current_place_and_drafts(self):
        category = self.place.categories.first()
        for index in range(6):
            other = make_place(name=f'Other {index}', slug=f'other-{index}', is_published=True)
            other.categories.add(category)
            PlaceImage.objects.create(place=other, image='other.png')
        response = self.client.get(self.place.get_absolute_url())
        more = list(response.context['more_places'])
        self.assertEqual(len(more), 4)
        self.assertNotIn(self.place, more)
        self.assertTrue(all(place.is_published for place in more))
        self.assertNotContains(response, 'Hidden draft')

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

    def test_admin_login_rejects_invalid_password(self):
        response = self.client.post('/admin/login/?next=/admin/', {'username': 'test-admin', 'password': 'wrong', 'next': '/admin/'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        response = self.client.post('/admin/login/?next=/admin/', {'username': 'test-admin', 'password': 'Test-password-827!', 'next': '/admin/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin_user.pk)

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

    def test_admin_map_fields_persist_and_feed_public_map_and_pdf(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/admin/attractions/place/add/')
        self.assertNotContains(response, 'name="opening_time"')
        self.assertNotContains(response, 'name="closing_time"')
        self.assertContains(response, 'name="opening_hours"')
        self.assertContains(response, 'name="opening_hours_note"')
        for field in ['google_maps_embed_url', 'google_maps_query', 'google_maps_place_id']:
            self.assertContains(response, f'name="{field}"')
        embed = 'https://www.google.com/maps/embed?pb=!1m18!staff-selected'
        data = self.payload(google_maps_embed_url=embed,
                            google_maps_query='Staff-selected museum, Sri Lanka',
                            google_maps_place_id='staff-selected-place-id',
                            **{'images-0-image': self.upload()})
        self.assertEqual(self.client.post('/admin/attractions/place/add/', data).status_code, 302)
        place = Place.objects.get(slug='admin-test')
        self.assertEqual(place.google_maps_embed_url, embed)
        self.assertEqual(place.google_maps_query, data['google_maps_query'])
        self.assertEqual(place.google_maps_place_id, data['google_maps_place_id'])
        self.assertContains(self.client.get(place.get_absolute_url()), embed)
        self.client.post(reverse('planner:add', args=[place.pk]))
        pdf = b''.join(self.client.get(reverse('planner:download_pdf')).streaming_content)
        self.assertIn(b'query=Staff-selected+museum%2C+Sri+Lanka', pdf)
        self.assertIn(b'query_place_id=staff-selected-place-id', pdf)

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

    def test_bulk_publish_skips_incomplete_and_denies_limited_staff(self):
        ready = make_place(slug='ready')
        ready.categories.add(self.category)
        PlaceImage.objects.create(place=ready, image='test.png')
        incomplete = make_place(slug='incomplete')
        data = {'action': 'publish_selected', '_selected_action': [ready.pk, incomplete.pk]}
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post('/admin/attractions/place/', data).status_code, 403)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.post('/admin/attractions/place/', data).status_code, 302)
        ready.refresh_from_db(); incomplete.refresh_from_db()
        self.assertTrue(ready.is_published)
        self.assertFalse(incomplete.is_published)

    def test_invalid_upload_and_radius_are_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.admin_user)
        data = self.payload(latitude='7.5', **{'images-0-image': SimpleUploadedFile('bad.png', b'not an image')})
        response = self.client.post('/admin/attractions/place/add/', data)
        self.assertContains(response, 'within 25 km')
        self.assertContains(response, 'Upload a valid image')
        self.assertFalse(Place.objects.exists())


class ContentImportTests(TestCase):
    def test_reference_dataset_import_is_draft_idempotent_and_within_radius(self):
        call_command('import_verified_places', stdout=StringIO())
        call_command('import_verified_places', stdout=StringIO())
        self.assertEqual(Place.objects.count(), 12)
        self.assertFalse(Place.objects.published().exists())
        proposed = {'kalutara-bodhiya', 'richmond-castle', 'panadura-beach',
                    'bolgoda-lake', 'kalutara-beach', 'wadduwa-beach'}
        slugs = set(Place.objects.values_list('slug', flat=True))
        self.assertTrue(proposed <= slugs)
        self.assertFalse({'kande-vihara', 'beruwala-lighthouse'} & slugs)
        beach = Place.objects.get(slug='wadduwa-beach')
        beach.description = 'Staff-reviewed description.'
        beach.save()
        call_command('import_verified_places', stdout=StringIO())
        beach.refresh_from_db()
        self.assertEqual(beach.description, 'Staff-reviewed description.')
        for place in Place.objects.all():
            self.assertLessEqual(place.distance_km, 25)
            self.assertGreater(place.categories.count(), 0)
            self.assertIn('https://commons.wikimedia.org/', place.visitor_information)
            self.assertIn('creativecommons.org', place.visitor_information)


    def test_visitor_update_preserves_custom_content_and_is_idempotent(self):
        call_command('import_verified_places', stdout=StringIO())
        museum = Place.objects.get(slug='air-force-museum')
        museum.opening_hours = ''
        museum.google_maps_embed_url = ''
        museum.google_maps_query = ''
        museum.visitor_information = 'Staff visitor guidance.\n\nPhoto: Preserved credit.'
        museum.save()
        temple = Place.objects.get(slug='kalutara-bodhiya')
        temple.opening_hours = 'Staff schedule: Sunday appointments only.'
        temple.google_maps_query = 'Staff selected destination'
        temple.save()
        call_command('update_visitor_details', stdout=StringIO())
        museum.refresh_from_db()
        temple.refresh_from_db()
        self.assertIn('Monday: Closed', museum.opening_hours)
        self.assertIn('Public holidays: Closed', museum.opening_hours)
        self.assertTrue(museum.google_maps_embed_url.startswith('https://www.google.com/maps/embed?pb='))
        self.assertTrue(museum.visitor_information.startswith('Staff visitor guidance.\n\nPhoto: Preserved credit.'))
        self.assertEqual(temple.opening_hours, 'Staff schedule: Sunday appointments only.')
        self.assertEqual(temple.google_maps_query, 'Staff selected destination')
        information = museum.visitor_information
        output = StringIO()
        call_command('update_visitor_details', stdout=output)
        museum.refresh_from_db()
        self.assertEqual(information, museum.visitor_information)
        self.assertIn('0 attraction(s)', output.getvalue())

    def test_reviewed_hours_import_and_update_preserve_staff_edits(self):
        call_command('import_verified_places', stdout=StringIO())
        temple = Place.objects.get(slug='bellanwila-viharaya')
        self.assertIn('6:00 AM–9:00 PM', temple.opening_hours)
        museum = Place.objects.get(slug='air-force-museum')
        self.assertIn('8:30 AM–4:15 PM', museum.opening_hours)
        self.assertIn('Monday: Closed', museum.opening_hours)
        zoo = Place.objects.get(slug='dehiwala-zoo')
        self.assertIn('8:30 AM–5:00 PM', zoo.opening_hours)
        temple.opening_hours = 'Staff schedule: 7 AM–8 PM'
        temple.save()
        museum.opening_hours = ''
        museum.visitor_information = 'Staff guidance.'
        museum.save()
        call_command('update_reference_hours', stdout=StringIO())
        temple.refresh_from_db()
        museum.refresh_from_db()
        self.assertEqual(temple.opening_hours, 'Staff schedule: 7 AM–8 PM')
        self.assertIn('8:30 AM–4:15 PM', museum.opening_hours)
        self.assertTrue(museum.visitor_information.startswith('Staff guidance.'))
        information = museum.visitor_information
        call_command('update_reference_hours', stdout=StringIO())
        museum.refresh_from_db()
        self.assertEqual(museum.visitor_information, information)


class WeeklyHoursMigrationTests(TransactionTestCase):
    def test_old_times_are_preserved_before_columns_are_removed(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        before = [('attractions', '0004_alter_place_google_maps_query')]
        after = [('attractions', '0005_use_weekly_opening_hours')]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(after))
        executor.migrate(before)
        OldPlace = executor.loader.project_state(before).apps.get_model('attractions', 'Place')
        cases = [
            ('06:00', '21:00', '', '06:00 - 21:00'),
            ('00:00', None, '', 'From 00:00'),
            (None, '17:00', '', 'Until 17:00'),
            (None, None, '', ''),
            ('06:00', '21:00', 'Monday: Closed', 'Monday: Closed'),
        ]
        for index, (opening, closing, weekly, expected) in enumerate(cases):
            OldPlace.objects.create(name='Migration test', slug=f'migration-{index}',
                                    latitude='6.714444', longitude='79.986667',
                                    opening_time=opening, closing_time=closing,
                                    opening_hours=weekly, opening_hours_note='Preserve note.')
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        for index, (_, _, _, expected) in enumerate(cases):
            place = Place.objects.get(slug=f'migration-{index}')
            self.assertEqual(place.opening_hours, expected)
            self.assertEqual(place.opening_hours_note, 'Preserve note.')


class ErrorPageTests(TestCase):
    def test_production_404(self):
        from django.test import override_settings
        with override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False):
            response = self.client.get('/not-a-real-page/')
            self.assertContains(response, 'This stop is unavailable', status_code=404)
            self.assertNotContains(response, 'Traceback', status_code=404)

    def test_production_500_renders_without_database_or_session(self):
        from django.test import RequestFactory
        from django.views.defaults import server_error

        with self.assertNumQueries(0):
            response = server_error(RequestFactory().get('/'))
        self.assertContains(response, 'We couldn’t load this page', status_code=500)
        self.assertContains(response, '/static/vendor/bootstrap/css/bootstrap.min.css', status_code=500)
        self.assertNotContains(response, 'Traceback', status_code=500)


class SubmissionDataTests(TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory / 'media')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.category = Category.objects.create(name='Nature', slug='nature', description='Staff category.')
        self.place = make_place(is_published=True, opening_hours='Monday: Closed\nTuesday: 9 AM–5 PM',
                                opening_hours_note='Staff exception.', visitor_information='Staff guidance and credit.',
                                google_maps_query='Staff named location', google_maps_place_id='staff-id',
                                google_maps_embed_url='https://www.google.com/maps/embed?pb=staff-map')
        self.place.categories.add(self.category)
        from io import BytesIO
        from PIL import Image
        from django.core.files.base import ContentFile
        data = BytesIO()
        Image.new('RGB', (10, 10), 'blue').save(data, format='PNG')
        for order in [0, 1]:
            photo = PlaceImage(place=self.place, alt_text=f'Staff photo {order}',
                               display_order=order, is_cover=order == 0)
            photo.image.save(f'photo-{order}.png', ContentFile(data.getvalue()), save=True)
        self.package = self.directory / 'package'
        call_command('export_submission_data', str(self.package), stdout=StringIO())

    def test_offline_round_trip_preserves_fields_categories_photos_and_publication(self):
        import hashlib
        import json
        manifest = json.loads((self.package / 'places.json').read_text())
        self.assertEqual(set(manifest), {'version', 'categories', 'places'})
        self.assertEqual(set(manifest['places'][0]), {'fields', 'categories', 'images'})
        original = Place.objects.values().get(pk=self.place.pk)
        self.place.delete()
        self.category.delete()
        call_command('import_submission_data', str(self.package), stdout=StringIO())
        restored = Place.objects.get(slug=original['slug'])
        for field, value in original.items():
            if field != 'id':
                self.assertEqual(getattr(restored, field), value, field)
        self.assertEqual(restored.categories.get().description, 'Staff category.')
        self.assertEqual(restored.images.count(), 2)
        for photo, record in zip(restored.images.all(), manifest['places'][0]['images']):
            self.assertEqual(photo.alt_text, record['alt_text'])
            self.assertEqual(photo.is_cover, record['is_cover'])
            with photo.image.open('rb') as content:
                self.assertEqual(hashlib.sha256(content.read()).hexdigest(), record['sha256'])
        self.assertContains(self.client.get('/attractions/'), restored.name)
        detail = self.client.get(restored.get_absolute_url())
        self.assertContains(detail, 'Tuesday: 9 AM–5 PM')
        self.assertContains(detail, 'https://www.google.com/maps/embed?pb=staff-map')

    def test_repeated_import_skips_existing_records_and_preserves_staff_edits(self):
        self.place.description = 'New staff description.'
        self.place.opening_hours = 'Staff replacement schedule.'
        self.place.save()
        photo_names = list(self.place.images.values_list('image', flat=True))
        for _ in range(2):
            output = StringIO()
            call_command('import_submission_data', str(self.package), stdout=output)
            self.assertIn('Imported 0 places; skipped 1', output.getvalue())
        self.place.refresh_from_db()
        self.assertEqual(self.place.description, 'New staff description.')
        self.assertEqual(self.place.opening_hours, 'Staff replacement schedule.')
        self.assertEqual(list(self.place.images.values_list('image', flat=True)), photo_names)
        self.assertEqual(Place.objects.count(), 1)

    def test_missing_corrupt_or_outside_image_is_rejected_before_import(self):
        import json
        from django.core.management import CommandError
        manifest_path = self.package / 'places.json'
        original = manifest_path.read_text()
        self.place.delete()
        self.category.delete()
        for file in ['images/missing.png', '../outside.png']:
            manifest = json.loads(original)
            manifest['places'][0]['images'][0]['file'] = file
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(CommandError):
                call_command('import_submission_data', str(self.package), stdout=StringIO())
            self.assertFalse(Place.objects.exists())
            self.assertFalse(Category.objects.exists())
        manifest = json.loads(original)
        manifest['places'][0]['images'][0]['sha256'] = 'wrong'
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesMessage(CommandError, 'checksum mismatch'):
            call_command('import_submission_data', str(self.package), stdout=StringIO())
        self.assertFalse(Place.objects.exists())

    def test_invalid_final_image_set_rolls_back_database_and_copied_files(self):
        import json
        from pathlib import Path
        from django.conf import settings
        from django.core.management import CommandError
        manifest_path = self.package / 'places.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['places'][0]['images'][1]['is_cover'] = True
        manifest_path.write_text(json.dumps(manifest))
        self.place.delete()
        self.category.delete()
        before = set(Path(settings.MEDIA_ROOT).rglob('*.png'))
        with self.assertRaises(CommandError):
            call_command('import_submission_data', str(self.package), stdout=StringIO())
        self.assertFalse(Place.objects.exists())
        self.assertFalse(Category.objects.exists())
        self.assertEqual(set(Path(settings.MEDIA_ROOT).rglob('*.png')), before)

    def test_export_refuses_overwrite_and_missing_source_photograph(self):
        from django.core.management import CommandError
        original = (self.package / 'places.json').read_bytes()
        with self.assertRaisesMessage(CommandError, 'Destination already exists'):
            call_command('export_submission_data', str(self.package), stdout=StringIO())
        self.assertEqual((self.package / 'places.json').read_bytes(), original)
        image = self.place.images.first()
        image.image.storage.delete(image.image.name)
        destination = self.directory / 'incomplete'
        with self.assertRaises(CommandError):
            call_command('export_submission_data', str(destination), stdout=StringIO())
        self.assertFalse(destination.exists())

    def test_missing_package_reports_actionable_error(self):
        from django.core.management import CommandError
        with self.assertRaisesMessage(CommandError, 'Import failed'):
            call_command('import_submission_data', str(self.directory / 'missing'), stdout=StringIO())
