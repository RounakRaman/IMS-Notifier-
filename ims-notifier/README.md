# IMS Notifier

Daily keyword watcher for the [IMS NSIT notifications board](https://www.imsnsit.org/imsnsit/notifications.php).
When a new notification matching any of your keywords is posted, you get an
email and a push notification on your phone.

## Repo layout

```
ims-notifier/
├── backend/              FastAPI web app + daily cron (deploys to Render)
│   ├── app.py            Dashboard + device-registration API
│   ├── check.py          Daily cron entry point
│   ├── scraper.py        IMS page fetcher + parser
│   ├── db.py             Postgres/SQLite layer
│   ├── notifier.py       Gmail SMTP + Firebase Cloud Messaging
│   ├── templates/        Jinja2 templates for the dashboard
│   └── requirements.txt
│
├── android-app/          Native Android app (sideload, no Play Store needed)
│   ├── app/
│   │   ├── src/main/...  Kotlin source + layouts
│   │   └── google-services.json   <-- YOU DROP THIS IN (see SETUP.md)
│   └── build.gradle.kts
│
├── docs/
│   └── SETUP.md          ← start here
│
└── render.yaml           One-click Render blueprint
```

## Quick start

Read **[docs/SETUP.md](docs/SETUP.md)**. It walks through every step:
Supabase, Gmail app password, Firebase project, Render deploy, Android app build.

## Cost

All free forever. Services used:
- Render free tier (web + cron)
- Supabase free tier (Postgres)
- Gmail SMTP (no cost)
- Firebase Cloud Messaging (free, unlimited)

## Features

- Dashboard for managing keywords (password-protected)
- Deduplication — you only ever get notified once per notification
- Multi-device push (install the Android app on any number of phones)
- Tappable pushes that open the IMS PDF/link directly
- Recent-matches feed in the dashboard
- Manual "Run Check Now" button for on-demand scraping
- Survives minor IMS page HTML changes (heuristic parser, not tied to brittle selectors)
