# Touch Typing Test — Django Web Port

A web port of the Textual terminal typing-test app, built with Django + vanilla JS.

## Setup

```bash
# 1. Create & activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dev server
python manage.py runserver
```

Apply the database schema once with `python manage.py migrate`, then open **http://127.0.0.1:8000** in your browser.

## Race rooms

Before starting, choose a guest identity or signed-in account, then choose a solo race or a friend room. A room creator is its host. Participants can join while the room is waiting; only the host can start the race. Once started, participants see live progress bars, WPM, and accuracy. The quote is randomly selected from a bundled collection, so races do not depend on an external quote API. New accounts can be created from the page; existing accounts can use **Sign in**.

The app uses database-backed race rooms and browser sessions. SQLite is suitable for local development and light use. For a busy public deployment, configure PostgreSQL through Django's `DATABASES` setting and run multiple Django workers behind an application server; the race API uses HTTP polling, so no WebSocket server is needed.

Run the checks with `python manage.py check` and the workflow tests with `python manage.py test core`.

## Keybindings (same as the original Textual app)

| Key | Action |
|-----|--------|
| `G` | Generate a new quote before joining a race |
| `R` | Reset the current test |
| `D` | Toggle dark / light theme |
| `Esc` | Reset (while typing) |

## Project structure

```
typing_test_django/
├── manage.py
├── requirements.txt
├── typing_test_django/       # Django project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── core/                     # Main app
    ├── views.py              # Account, quote, and race endpoints
    ├── models.py             # Isolated race rooms and participants
    ├── migrations/           # Database schema
    ├── tests.py              # Race flow and account tests
    ├── urls.py
    └── templates/
        └── core/
            └── index.html    # All UI + JS logic lives here
```

## How it maps to the original app

| Textual | Django / Web |
|---------|-------------|
| `TypingTest.compose()` | `index()` view renders `index.html` |
| `action_regenerate()` | `/quote/` endpoint (calls httpx internally) |
| `handle_input_changed()` | `input` event listener in JS |
| `update_wpm()` | `updateWpm()` in JS |
| `action_reset()` | `actionReset()` in JS |
| `StatusBar` reactive | DOM updates via `setStatus()` / `setWpm()` |
| `Input.error` CSS class | `#input-field.error` CSS class |
| `BINDINGS` | `keydown` listener |
| `Header(show_clock=True)` | `tickClock()` updating `#clock` |
