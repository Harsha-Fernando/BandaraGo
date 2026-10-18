from django.test import Client, TestCase
from django.urls import reverse

from attractions.models import Category, PlaceImage
from attractions.tests import make_place
from .views import SESSION_KEY


class PlannerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Nature', slug='nature')
        cls.places = []
        for i in range(3):
            place = make_place(name=f'Test stop {i}', slug=f'stop-{i}', is_published=True)
            place.categories.add(category)
            PlaceImage.objects.create(place=place, image='synthetic.png')
            cls.places.append(place)
        cls.a, cls.b, cls.c = cls.places

    def add(self, place):
        return self.client.post(reverse('planner:add', args=[place.pk]))

    def test_add_order_duplicates_and_session_isolation(self):
        self.add(self.b); self.add(self.a); self.add(self.b)
        self.assertEqual(self.client.session[SESSION_KEY], [self.b.pk, self.a.pk])
        self.assertNotContains(Client().get('/planner/'), self.a.name)
        response = self.client.get('/planner/')
        self.assertEqual([p.pk for p in response.context['places']], [self.b.pk, self.a.pk])

    def test_reorder_and_boundaries(self):
        for place in self.places: self.add(place)
        url = reverse('planner:reorder', args=[self.b.pk])
        self.client.post(url, {'direction': 'up'})
        self.assertEqual(self.client.session[SESSION_KEY], [self.b.pk, self.a.pk, self.c.pk])
        self.client.post(url, {'direction': 'up'})
        self.client.post(url, {'direction': 'down'})
        self.assertEqual(self.client.session[SESSION_KEY], [p.pk for p in self.places])
        self.assertEqual(self.client.post(url, {'direction': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post('/planner/reorder/99999/', {'direction': 'up'}).status_code, 400)

    def test_removal_and_clear_require_confirmation(self):
        self.add(self.a); self.add(self.b)
        confirm = self.client.get(reverse('planner:confirm_remove', args=[self.a.pk]))
        self.assertContains(confirm, 'Keep my plan')
        self.assertEqual(len(self.client.session[SESSION_KEY]), 2)
        url = reverse('planner:remove', args=[self.a.pk])
        self.assertEqual(self.client.post(url).status_code, 400)
        self.client.post(url, {'confirmed': 'yes'})
        self.assertEqual(self.client.session[SESSION_KEY], [self.b.pk])
        self.assertContains(self.client.get('/planner/clear/confirm/'), 'Clear your entire plan?')
        self.assertEqual(self.client.post('/planner/clear/').status_code, 400)
        self.client.post('/planner/clear/', {'confirmed': 'yes'})
        self.assertEqual(self.client.session[SESSION_KEY], [])

    def test_mutations_reject_get_and_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        for url in [reverse('planner:add', args=[self.a.pk]), reverse('planner:reorder', args=[self.a.pk]), reverse('planner:remove', args=[self.a.pk]), '/planner/clear/']:
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(strict.post(url).status_code, 403)

    def test_deleted_unpublished_and_malformed_session(self):
        session = self.client.session
        session[SESSION_KEY] = [self.a.pk, self.a.pk, None, {}, True, 'bad', 2**100, self.b.pk]
        session.save()
        self.b.is_published = False; self.b.save()
        response = self.client.get('/planner/')
        self.assertEqual([p.pk for p in response.context['places']], [self.a.pk])
        self.assertEqual(self.add(self.b).status_code, 404)
        self.a.delete()
        self.assertContains(self.client.get('/planner/'), 'Every good day starts somewhere')
        self.assertEqual(self.client.post('/planner/add/99999/').status_code, 404)
        session = self.client.session; session[SESSION_KEY] = 'invalid'; session.save()
        self.assertEqual(self.client.get('/planner/').status_code, 200)

    def test_detail_has_add_form(self):
        response = self.client.get(self.a.get_absolute_url())
        self.assertContains(response, 'Add to Plan')
        self.assertContains(response, reverse('planner:add', args=[self.a.pk]))

    def test_navigation_count_matches_valid_unique_session_places(self):
        session = self.client.session
        session[SESSION_KEY] = [self.a.pk, self.a.pk, self.b.pk, None, 'bad']
        session.save()
        self.b.is_published = False
        self.b.save()
        for url in ['/', self.c.get_absolute_url(), '/planner/']:
            response = self.client.get(url)
            self.assertEqual(response.context['plan_count'], 1)
            self.assertContains(response, 'aria-label="1 selected places"')
        self.client.post('/planner/clear/', {'confirmed': 'yes'})
        self.assertEqual(self.client.get('/').context['plan_count'], 0)

    def test_only_routine_messages_auto_dismiss(self):
        from django.contrib import messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from django.template.loader import render_to_string
        request = RequestFactory().get('/')
        request.session = {}
        request._messages = FallbackStorage(request)
        messages.success(request, 'Saved successfully.')
        messages.info(request, 'Already selected.')
        messages.error(request, 'Validation failed.')
        html = render_to_string('base.html', request=request)
        self.assertEqual(html.count('data-auto-dismiss'), 2)
        self.assertEqual(html.count('aria-label="Dismiss notification"'), 3)
        error_alert = html.split('alert-danger', 1)[1].split('</div>', 1)[0]
        self.assertNotIn('data-auto-dismiss', error_alert)

    def test_pdf_download_has_ordered_map_links_and_is_private(self):
        self.add(self.c)
        self.add(self.a)
        response = self.client.get(reverse('planner:download_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('bandarago-one-day-plan.pdf', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        pdf = b''.join(response.streaming_content)
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertLess(pdf.index(self.c.map_url.encode()), pdf.index(self.a.map_url.encode()))
        self.assertNotIn(self.b.map_url.encode(), pdf)
        self.assertEqual(self.client.session[SESSION_KEY], [self.c.pk, self.a.pk])

    def test_pdf_empty_plan_and_session_isolation(self):
        self.add(self.a)
        response = Client().get(reverse('planner:download_pdf'))
        self.assertRedirects(response, reverse('planner:detail'))
        self.assertContains(self.client.get('/planner/'), 'Download plan as PDF')
        self.assertNotContains(Client().get('/planner/'), 'Download plan as PDF')
        self.assertEqual(self.client.post(reverse('planner:download_pdf')).status_code, 405)

    def test_pdf_omits_unpublished_duplicates_and_invalid_session_values(self):
        session = self.client.session
        session[SESSION_KEY] = [self.b.pk, self.a.pk, self.b.pk, None, {}, True, 'bad', 2**100]
        session.save()
        self.a.is_published = False
        self.a.save()
        response = self.client.get(reverse('planner:download_pdf'))
        pdf = b''.join(response.streaming_content)
        self.assertNotIn(self.a.map_url.encode(), pdf)
        self.assertEqual(pdf.count(self.b.map_url.encode()), 1)

    def test_pdf_handles_long_names_and_special_characters(self):
        self.a.name = 'Museum & Gardens <West> ' + 'Visitor centre ' * 8
        self.a.address = 'Main road & Lake <West> ' * 10
        self.a.save()
        self.add(self.a)
        response = self.client.get(reverse('planner:download_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
