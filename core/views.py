import random
import string
import httpx

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_GET, require_POST

from .models import RaceParticipant, RaceSession


QUOTE_API_URL = 'https://dummyjson.com/quotes/random'
QUOTE_FALLBACK = (
    'Take a breath, find your rhythm, and keep moving forward. Each careful step gives you '
    'a little more confidence, and every new attempt is a chance to discover what you can do.'
)


def fetch_random_quote():
    """Fetch one quote from DummyJSON, using a local safety net if it is unavailable."""
    try:
        response = httpx.get(QUOTE_API_URL, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        quote = payload.get('quote', '').strip()
        author = payload.get('author', '').strip()
        if not quote:
            raise ValueError('The quote API returned an empty quote.')
        return quote[:1000], author[:120]
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return QUOTE_FALLBACK, ''


def index(request):
    return render(request, 'core/index.html')


@require_GET
def random_quote(request):
    quote, author = fetch_random_quote()
    return JsonResponse({'quote': quote, 'author': author})


@require_POST
def signup(request):
    form = UserCreationForm(request.POST)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('index')
    return render(request, 'core/index.html', {'signup_errors': form.errors.get_json_data()})


def _participant_identity(request, requested_name=''):
    if not request.session.session_key:
        request.session.create()
    name = request.user.username if request.user.is_authenticated else requested_name.strip()
    if not name:
        name = 'Guest-' + ''.join(random.choices(string.digits, k=4))
    return request.session.session_key, name[:32]


@require_POST
def create_race(request):
    session_key, name = _participant_identity(request, request.POST.get('name', ''))
    quote = request.POST.get('quote', '').strip()
    if not quote:
        quote, _ = fetch_random_quote()
    race = RaceSession.objects.create(code=RaceSession.new_code(), quote=quote[:1000])
    RaceParticipant.objects.create(race=race, session_key=session_key, display_name=name,
                                   user=request.user if request.user.is_authenticated else None,
                                   is_host=True)
    return JsonResponse({'code': race.code, 'quote': race.quote, 'name': name})


@require_POST
def join_race(request, code):
    race = get_object_or_404(RaceSession, code=code.upper())
    if race.started_at is not None:
        return JsonResponse({'error': 'This race has already started.'}, status=409)
    session_key, name = _participant_identity(request, request.POST.get('name', ''))
    participant, created = RaceParticipant.objects.get_or_create(
        race=race, session_key=session_key,
        defaults={'display_name': name, 'user': request.user if request.user.is_authenticated else None},
    )
    if not created and participant.finished_at is None:
        participant.display_name = name
        participant.save(update_fields=['display_name'])
    return JsonResponse({'code': race.code, 'quote': race.quote, 'name': participant.display_name})


@require_GET
def race_state(request, code):
    race = get_object_or_404(RaceSession, code=code.upper())
    now = timezone.now()
    starts_at = race.started_at
    participants = list(race.participants.order_by('-progress', 'joined_at'))
    return JsonResponse({
        'code': race.code, 'quote': race.quote,
        'started': bool(starts_at and starts_at <= now),
        'starts_at': int(starts_at.timestamp() * 1000) if starts_at else None,
        'can_start': bool(starts_at is None and request.session.session_key and race.participants.filter(
            session_key=request.session.session_key, is_host=True).exists()),
        'participant_count': len(participants),
        'participants': [{'name': p.display_name, 'progress': p.progress, 'wpm': p.wpm,
                          'accuracy': p.accuracy, 'finished': p.finished_at is not None}
                         for p in participants],
    })


@require_POST
def start_race(request, code):
    key = request.session.session_key
    if not key:
        return JsonResponse({'error': 'Join this room before starting it.'}, status=403)
    with transaction.atomic():
        race = get_object_or_404(RaceSession.objects.select_for_update(), code=code.upper())
        host = race.participants.filter(session_key=key, is_host=True).exists()
        if not host:
            return JsonResponse({'error': 'Only the room host can start this race.'}, status=403)
        if race.started_at is None:
            race.started_at = timezone.now() + timedelta(seconds=5)
            race.save(update_fields=['started_at'])
    return JsonResponse({
        'ok': True,
        'starts_at': int(race.started_at.timestamp() * 1000),
        'started': race.started_at <= timezone.now(),
    })


@require_POST
def change_race_quote(request, code):
    key = request.session.session_key
    if not key:
        return JsonResponse({'error': 'Join this room before changing its quote.'}, status=403)
    with transaction.atomic():
        race = get_object_or_404(RaceSession.objects.select_for_update(), code=code.upper())
        host = race.participants.filter(session_key=key, is_host=True).exists()
        if not host:
            return JsonResponse({'error': 'Only the room host can change this quote.'}, status=403)
        if race.started_at is not None:
            return JsonResponse({'error': 'The quote is locked once the race starts.'}, status=409)
        race.quote, _ = fetch_random_quote()
        race.save(update_fields=['quote'])
    return JsonResponse({'ok': True, 'quote': race.quote})


@require_POST
def update_progress(request, code):
    race = get_object_or_404(RaceSession, code=code.upper())
    key, _ = _participant_identity(request)
    participant = get_object_or_404(RaceParticipant, race=race, session_key=key)
    if race.started_at is None or race.started_at > timezone.now():
        return JsonResponse({'error': 'The host has not started this race yet.'}, status=409)
    try:
        progress = max(0, min(100, int(request.POST.get('progress', '0'))))
        wpm = max(0, min(999, int(request.POST.get('wpm', '0'))))
        accuracy = max(0, min(100, int(request.POST.get('accuracy', '0'))))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid race stats.'}, status=400)
    if participant.finished_at is None:
        progress = max(participant.progress, progress)
        participant.progress, participant.wpm, participant.accuracy = progress, wpm, accuracy
        fields = ['progress', 'wpm', 'accuracy']
        if progress == 100:
            participant.finished_at = timezone.now()
            fields.append('finished_at')
        participant.save(update_fields=fields)
    return JsonResponse({'ok': True})
