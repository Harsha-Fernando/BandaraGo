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
        self.assertContains(response, 'Add to my day')
        self.assertContains(response, reverse('planner:add', args=[self.a.pk]))
