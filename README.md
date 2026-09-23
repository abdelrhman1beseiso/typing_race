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

Before starting a race, choose **Continue as guest** or select the signed-in account. Guests receive a browser-session identity; accounts use Django's built-in authentication. Choose **Start a new race** to create a room and share its six-character code, or enter a code to join an existing room. Typing progress and results are stored per room and refreshed for other racers about once per second. Each room has its own quote and participant list. New accounts can be created from the page; existing accounts can use **Sign in**.

The app uses database-backed race rooms and browser sessions. SQLite is suitable for local development and light use. For a busy public deployment, configure PostgreSQL through Django's `DATABASES` setting and run multiple Django workers behind an application server; the race API is HTTP polling, so no WebSocket server is needed. Quote loading falls back to bundled sample quotes when the external quote API is unavailable.

Run the checks with `python manage.py check` and the workflow tests with `python manage.py test core`.

## Keybindings (same as the original Textual app)

| Key | Action |
|-----|--------|
| `G` | Generate a new quote |
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
