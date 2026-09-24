from django.contrib.auth.models import User
from django.test import TestCase
import httpx
from unittest.mock import patch

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
        self.assertEqual(self.client.post(f'/race/{code}/progress/', {
            'progress': 1, 'wpm': 1, 'accuracy': 1,
        }).status_code, 409)
        self.assertEqual(self.client.post(f'/race/{code}/start/').status_code, 200)
        response = self.client.post(f'/race/{code}/progress/', {'progress': 50, 'wpm': 42, 'accuracy': 96})
        self.assertEqual(response.status_code, 200)
        state = self.client.get(f'/race/{code}/state/').json()
        self.assertTrue(state['started'])
        self.assertEqual(state['participants'][0]['progress'], 50)
        self.assertEqual(state['participants'][0]['wpm'], 42)

    def test_progress_is_bounded_and_invalid_data_rejected(self):
        code = self.create_room().json()['code']
        self.client.post(f'/race/{code}/start/')
        response = self.client.post(f'/race/{code}/progress/', {'progress': 999, 'wpm': 5000, 'accuracy': -2})
        self.assertEqual(response.status_code, 200)
        participant = RaceParticipant.objects.get(race__code=code)
        self.assertEqual((participant.progress, participant.wpm, participant.accuracy), (100, 999, 0))
        invalid = self.client.post(f'/race/{code}/progress/', {'progress': 'bad'})
        self.assertEqual(invalid.status_code, 400)

    def test_host_starts_room_and_joiners_wait(self):
        code = self.create_room().json()['code']
        joiner = self.client_class()
        self.assertEqual(joiner.post(f'/race/{code}/join/', {'name': 'Guest Two'}).status_code, 200)
        joiner_state = joiner.get(f'/race/{code}/state/').json()
        self.assertFalse(joiner_state['started'])
        self.assertFalse(joiner_state['can_start'])
        self.assertTrue(self.client.get(f'/race/{code}/state/').json()['can_start'])
        self.assertEqual(joiner.post(f'/race/{code}/start/').status_code, 403)
        self.assertEqual(self.client.post(f'/race/{code}/start/').status_code, 200)
        self.assertTrue(joiner.get(f'/race/{code}/state/').json()['started'])
        self.assertEqual(joiner.post(f'/race/{code}/join/', {'name': 'Late guest'}).status_code, 409)

    def test_only_host_can_change_quote_before_race_and_quote_syncs(self):
        code = self.create_room().json()['code']
        original_quote = RaceSession.objects.get(code=code).quote
        joiner = self.client_class()
        joiner.post(f'/race/{code}/join/', {'name': 'Guest Two'})

        denied = joiner.post(f'/race/{code}/quote/')
        self.assertEqual(denied.status_code, 403)

        with patch('core.views.fetch_random_quote', return_value=('A fresh room quote from the API.', 'Writer')):
            changed = self.client.post(f'/race/{code}/quote/')
        self.assertEqual(changed.status_code, 200)
        self.assertNotEqual(changed.json()['quote'], original_quote)
        self.assertEqual(joiner.get(f'/race/{code}/state/').json()['quote'], changed.json()['quote'])

        self.client.post(f'/race/{code}/start/')
        locked = self.client.post(f'/race/{code}/quote/')
        self.assertEqual(locked.status_code, 409)

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
        with patch('core.views.fetch_random_quote', return_value=('A longer quote from the API.', 'A. Writer')):
            response = self.client.get('/quote/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'quote': 'A longer quote from the API.', 'author': 'A. Writer'})

    def test_quote_api_failure_uses_long_fallback(self):
        with patch('core.views.httpx.get', side_effect=httpx.ConnectError('offline')):
            response = self.client.get('/quote/')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()['quote']), 100)
