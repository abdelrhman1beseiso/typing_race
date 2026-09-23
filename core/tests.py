import json

from django.contrib.auth.models import User
from django.test import TestCase

from .models import RaceParticipant, RaceSession


class RaceFlowTests(TestCase):
    def create_room(self):
        return self.client.post('/race/create/', {'name': 'Guest One', 'quote': 'Race quote'} )

    def test_guest_can_create_race_and_room_is_isolated(self):
        first = self.create_room()
        self.assertEqual(first.status_code, 200)
        code = first.json()['code']
        self.assertEqual(first.json()['quote'], 'Race quote')
        self.assertEqual(RaceSession.objects.count(), 1)
        self.assertEqual(RaceParticipant.objects.filter(race__code=code).count(), 1)

        second_client = self.client_class()
        second = second_client.post(f'/race/{code}/join/', {'name': 'Guest Two'})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(RaceParticipant.objects.filter(race__code=code).count(), 2)
        other = second_client.post('/race/create/', {'name': 'Guest Two', 'quote': 'Other quote'})
        self.assertNotEqual(code, other.json()['code'])
        self.assertEqual(RaceParticipant.objects.filter(race__code=other.json()['code']).count(), 1)

    def test_progress_is_saved_and_visible_to_room(self):
        code = self.create_room().json()['code']
        response = self.client.post(f'/race/{code}/progress/', {'progress': 50, 'wpm': 42, 'accuracy': 96})
        self.assertEqual(response.status_code, 200)
        state = self.client.get(f'/race/{code}/state/').json()
        self.assertTrue(state['started'])
        self.assertEqual(state['participants'][0]['progress'], 50)
        self.assertEqual(state['participants'][0]['wpm'], 42)

    def test_progress_is_bounded_and_invalid_data_rejected(self):
        code = self.create_room().json()['code']
        response = self.client.post(f'/race/{code}/progress/', {'progress': 999, 'wpm': 5000, 'accuracy': -2})
        self.assertEqual(response.status_code, 200)
        participant = RaceParticipant.objects.get(race__code=code)
        self.assertEqual((participant.progress, participant.wpm, participant.accuracy), (100, 999, 0))
        invalid = self.client.post(f'/race/{code}/progress/', {'progress': 'bad'})
        self.assertEqual(invalid.status_code, 400)

    def test_signup_logs_user_in_and_user_is_attached_to_race(self):
        response = self.client.post('/account/signup/', {
            'username': 'runner', 'password1': 'Strong-test-pass-2026', 'password2': 'Strong-test-pass-2026',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='runner').exists())
        room = self.client.post('/race/create/', {'quote': 'Account quote'})
        self.assertEqual(room.status_code, 200)
        participant = RaceParticipant.objects.get(race__code=room.json()['code'])
        self.assertEqual(participant.user.username, 'runner')

    def test_random_quote_has_fallback_shape(self):
        response = self.client.get('/quote/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['quote'])
