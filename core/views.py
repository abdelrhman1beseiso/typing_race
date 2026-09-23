import random
import string

import httpx
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import RaceParticipant, RaceSession


FALLBACK_QUOTES = [
    'The secret of getting ahead is getting started.',
    'Great things are done by a series of small things brought together.',
    'It always seems impossible until it is done.',
]


def index(request):
    return render(request, 'core/index.html')


@require_GET
def random_quote(request):
    try:
        res = httpx.get('https://dummyjson.com/quotes/random', timeout=5.0)
        res.raise_for_status()
        data = res.json()
        if not isinstance(data.get('quote'), str) or not data['quote'].strip():
            raise ValueError('Quote service returned invalid data')
        return JsonResponse({'quote': data['quote'], 'author': data.get('author', '')})
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError):
        return JsonResponse({'quote': random.choice(FALLBACK_QUOTES), 'author': ''})


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
        quote = random.choice(FALLBACK_QUOTES)
    race = RaceSession.objects.create(code=RaceSession.new_code(), quote=quote[:1000])
    RaceParticipant.objects.create(race=race, session_key=session_key, display_name=name,
                                   user=request.user if request.user.is_authenticated else None)
    return JsonResponse({'code': race.code, 'quote': race.quote, 'name': name})


@require_POST
def join_race(request, code):
    race = get_object_or_404(RaceSession, code=code.upper())
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
    participants = list(race.participants.order_by('-progress', 'joined_at'))
    return JsonResponse({
        'code': race.code, 'quote': race.quote,
        'started': race.started_at is not None,
        'participants': [{'name': p.display_name, 'progress': p.progress, 'wpm': p.wpm,
                          'accuracy': p.accuracy, 'finished': p.finished_at is not None}
                         for p in participants],
    })


@require_POST
def update_progress(request, code):
    race = get_object_or_404(RaceSession, code=code.upper())
    key, _ = _participant_identity(request)
    participant = get_object_or_404(RaceParticipant, race=race, session_key=key)
    try:
        progress = max(0, min(100, int(request.POST.get('progress', '0'))))
        wpm = max(0, min(999, int(request.POST.get('wpm', '0'))))
        accuracy = max(0, min(100, int(request.POST.get('accuracy', '0'))))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid race stats.'}, status=400)
    if participant.finished_at is None:
        participant.progress, participant.wpm, participant.accuracy = progress, wpm, accuracy
        fields = ['progress', 'wpm', 'accuracy']
        if progress == 100:
            participant.finished_at = timezone.now()
            fields.append('finished_at')
        participant.save(update_fields=fields)
        if race.started_at is None:
            race.started_at = timezone.now()
            race.save(update_fields=['started_at'])
    return JsonResponse({'ok': True})
