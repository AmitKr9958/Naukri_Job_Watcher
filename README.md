# Naukri Job Watcher

Independent read-only Naukri job watcher. It is completely separate from `Naukri_refresh`.

## Locations
Delhi/NCR, Delhi, New Delhi, Gurgaon, Gurugram, Noida, Jaipur, Remote.

## Behaviour
- Searches every configured keyword/location combination.
- Keeps jobs that appear to be within the last 24 hours.
- Paginates available result pages and deduplicates by URL/job key.
- Opens new jobs and extracts the full page text for scoring.
- Uses deterministic keyword scoring first; OpenRouter is optional.
- Sends new qualifying matches to Telegram.
- Never submits applications.
- Stores history in local SQLite.
- Uses a dedicated persistent browser profile in this repository.

## First setup
1. Activate the venv.
2. Install dependencies: `pip install -r requirements.txt`.
3. Install Playwright Chromium: `python -m playwright install chromium`.
4. Copy `.env.example` to `.env` and add Telegram/OpenRouter credentials locally.
5. Run the watcher once with `python .\\src\\main.py`.
6. If Naukri requests manual login/OTP/CAPTCHA, complete it manually in this project's browser session. Do not bypass security controls.
7. After validation, install the Windows scheduled task with `powershell -ExecutionPolicy Bypass -File .\\scripts\\install_task.ps1`.

## Important
`browser_profile/`, `.env`, SQLite data and logs are intentionally excluded from Git. Never reuse the `Naukri_refresh` browser profile.

## Limitations
Naukri controls ranking, pagination and access, so no watcher can honestly guarantee every hidden job. This project systematically searches the configured combinations and deduplicates the accessible results.
