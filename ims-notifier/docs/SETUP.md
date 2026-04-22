# IMS Notifier — Setup Guide

A daily-scraping notifier for the IMS NSIT notifications board. When a new
notification appears that matches any of your keywords, you get an email and
a push notification on your phone.

**Stack**
- Backend: FastAPI on Render (free web service + free cron)
- Database: Supabase Postgres (free, no expiry)
- Email: Gmail SMTP
- Push: Firebase Cloud Messaging (FCM)
- Mobile: Custom Android app (sideloaded, no Play Store needed)

**Total cost: $0.** Time to set up end to end: about 90 minutes.

---

## 0. What you need before you start

1. A GitHub account (free)
2. A Gmail account (for sending the emails)
3. A Google account (for Firebase)
4. Android Studio installed on your computer ([download](https://developer.android.com/studio))
5. An Android phone with a USB cable, or the ability to sideload APKs

---

## 1. Put the code on GitHub

1. Create a new **private** GitHub repo called `ims-notifier`
2. Push the contents of this project folder to it:

```bash
cd ims-notifier
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ims-notifier.git
git push -u origin main
```

> Keep it private — the backend URL, Firebase config, and secrets trace back to you.

---

## 2. Create the Supabase database

1. Go to https://supabase.com, sign up, create a new project.
   - Choose a region close to India (e.g. Mumbai, Singapore)
   - Set a strong database password and save it in a password manager
2. Wait ~2 minutes for the project to provision
3. In the left sidebar, click **Project Settings → Database**
4. Scroll to **Connection string → URI**. Copy the string. It looks like:

```
postgresql://postgres.abcdef:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

**Save this.** You'll paste it into Render as `DATABASE_URL`.

That's all for Supabase. The backend creates its own tables on first run.

---

## 3. Create a Gmail App Password

You cannot use your regular Gmail password. You need an "App Password" which
is a separate 16-char password for programs to use.

1. Make sure 2-Step Verification is ON at https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. App name: `IMS Notifier`. Click Create.
4. Copy the 16-character password (remove the spaces). Save it.

You'll use:
- `SMTP_USER` = your Gmail address (e.g. `youraddress@gmail.com`)
- `SMTP_PASSWORD` = that 16-char app password
- `EMAIL_TO` = `raman.rounak@gmail.com`

---

## 4. Create the Firebase project (for push notifications)

### 4a. Create the project

1. Go to https://console.firebase.google.com
2. Click **Add project**. Name it `IMS Notifier`. Disable Google Analytics (you don't need it).
3. Wait for creation.

### 4b. Register the Android app

1. On the project home, click the **Android** icon ("Add app → Android").
2. **Android package name**: `com.rounak.imsnotifier` (exactly this string — it
   must match what's in `android-app/app/build.gradle.kts`).
3. App nickname: `IMS Notifier`. SHA-1: leave blank.
4. Click **Register app**.
5. Click **Download `google-services.json`**.
6. Save it. You'll drop it into `android-app/app/google-services.json` in Step 7.
7. Skip through the remaining SDK setup screens — the Gradle config is already done.

### 4c. Generate a service account key (for the backend to send pushes)

1. In Firebase console, click the gear icon → **Project settings**
2. Go to the **Service accounts** tab
3. Click **Generate new private key**. Confirm. A JSON file downloads.
4. Open the file. You'll paste its **entire contents** as one environment
   variable `FCM_SERVICE_ACCOUNT_JSON` in Render (step 5).

> Treat this JSON like a password. Anyone with it can send pushes to your users.

---

## 5. Deploy the backend on Render

1. Go to https://render.com, sign up with GitHub
2. Click **New → Blueprint**
3. Connect your GitHub account, pick the `ims-notifier` repo
4. Render reads `render.yaml` and proposes two services:
   - `ims-notifier-web` (the dashboard)
   - `ims-notifier-daily` (the cron job)
5. Click **Apply**. It will fail the first build because env vars aren't set.
   That's expected.

### 5a. Set environment variables on BOTH services

In the Render dashboard, open each service (`ims-notifier-web` and
`ims-notifier-daily`), go to **Environment**, and set:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | The Supabase URI from step 2 |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | The 16-char app password from step 3 |
| `EMAIL_TO` | `raman.rounak@gmail.com` |
| `FCM_SERVICE_ACCOUNT_JSON` | **The entire JSON file contents from step 4c, pasted as one string** |

On the web service only, also set:

| Variable | Value |
|----------|-------|
| `ADMIN_PASSWORD` | Choose any password. You'll use it to log in to the dashboard. |

Hit **Save Changes** on each. Render will redeploy.

### 5b. Verify

Open `https://ims-notifier-web.onrender.com` (your URL will be similar but
with a different suffix). You should see the login page. Log in with the
`ADMIN_PASSWORD` you set. Add a keyword like `CVSPK`. Click **Run Check Now**
to trigger the scraper on demand.

> **About the free web service sleeping**: Render's free web tier spins down
> after 15 min of inactivity and takes ~30 seconds to wake on the next request.
> That's fine because you only visit the dashboard occasionally. The cron job
> runs independently and does not sleep.

### 5c. Note your web service URL

You'll need it for the Android app. It looks like:
`https://ims-notifier-web-xxxx.onrender.com`

---

## 6. Build the Android app

### 6a. Open the project

1. Launch Android Studio
2. **File → Open**, select the `android-app/` folder
3. Wait for Gradle to sync (2–5 minutes the first time)

### 6b. Drop in the Firebase config

Copy the `google-services.json` file you downloaded in step 4b into:

```
android-app/app/google-services.json
```

Delete `android-app/app/PLACEHOLDER.txt` if you want.

### 6c. Point the app at your backend

Open `android-app/gradle.properties` and change:

```properties
BACKEND_URL=https://ims-notifier-web.onrender.com
```

to the actual URL from step 5c. **No trailing slash.**

### 6d. Generate the Gradle wrapper

The wrapper JAR isn't checked in. Android Studio will offer to generate it
automatically the first time you open the project. If it doesn't, run in the
Android Studio terminal:

```bash
gradle wrapper --gradle-version 8.9
```

### 6e. Build and install on your phone

Easiest path — direct install via USB:

1. On your phone: **Settings → About phone → tap "Build number" 7 times**
   to unlock Developer Options
2. **Settings → Developer options → Enable USB debugging**
3. Connect your phone via USB. Accept the "Allow USB debugging?" prompt.
4. In Android Studio, your phone appears in the device dropdown at the top.
5. Click the green **▶ Run** button.

The app installs and launches. It will:
1. Ask permission to show notifications → tap **Allow**
2. Fetch its FCM token
3. POST the token to your backend (`/api/device`)
4. Show "Registered. You'll get pushes." in red

If you want an APK to share across devices: **Build → Build Bundle(s)/APK(s)
→ Build APK(s)**. The APK appears in `android-app/app/build/outputs/apk/debug/`.
You can email it to yourself and install it on any phone with "Install unknown
apps" enabled.

---

## 7. Test the whole pipeline

1. On the dashboard, add a broad test keyword like `notice` or `exam` (something
   guaranteed to match something on the IMS page)
2. Click **Run Check Now**
3. Within a few seconds you should get:
   - An email at `raman.rounak@gmail.com`
   - A push notification on your phone
4. Tap the notification → the IMS PDF link opens
5. Delete the test keyword, add your real ones (`CVSPK`, etc.)

The cron fires once per day at **09:00 IST** (03:30 UTC). You can change this
in `render.yaml` — the `schedule:` field uses standard cron syntax. Edit and
push to GitHub; Render auto-redeploys.

---

## 8. Ongoing use

### Adding keywords later
Just visit the dashboard, add them in the **Watchlist** card. No redeploy needed.

### Adding more devices
Install the APK on another phone. It registers automatically. Pushes go to all
registered devices.

### Checking what's been matched
The dashboard shows the 30 most recent matches at the bottom.

### Changing your email recipient
Edit `EMAIL_TO` env var on both Render services. Use a comma-separated list for
multiple recipients (e.g. `raman.rounak@gmail.com,backup@gmail.com`).

---

## 9. Troubleshooting

**Email doesn't arrive**
- Check the cron job's logs in Render. If you see `smtplib.SMTPAuthenticationError`,
  your app password is wrong. Regenerate it.
- Gmail sometimes puts the first auto-mail in Spam. Mark it "Not spam".

**Push doesn't arrive**
- Check the cron logs for `FCM send failed`
- Make sure `FCM_SERVICE_ACCOUNT_JSON` is pasted correctly (it's a long string;
  Render accepts multi-line JSON fine)
- On the phone, battery optimization can throttle FCM. Go to **Settings → Apps
  → IMS Notifier → Battery → Unrestricted**.

**Scraper returns 0 notifications**
- IMS may have blocked your Render IP temporarily. Try again in a few hours.
- The site structure may have changed. Check cron logs for parser warnings.
  `scraper.py` uses heuristic parsing that survives minor changes, but a major
  redesign would need the parser updated.

**Dashboard loads slowly**
- Free tier spins down after 15 min. First load takes ~30 sec. Subsequent
  loads are fast until the next idle period.

**Supabase reports "database paused"**
- Supabase pauses free-tier projects after 1 week of no activity. Log into
  supabase.com and click **Restore**. The daily cron's writes count as
  activity, so this shouldn't happen in practice once you're running.

---

## 10. Architecture at a glance

```
+-----------------+       daily @ 09:00 IST       +---------------------+
|  Render Cron    | ----- scrapes ---------->     | imsnsit.org         |
|  check.py       | <----- HTML --------------    | notifications.php   |
+--------+--------+                                +---------------------+
         |
         | filter by keywords, dedupe
         v
+-----------------+   stores seen hashes    +---------------------+
|  Supabase       | <---------------------- |                     |
|  Postgres       |                         |                     |
+-----------------+                         |                     |
         ^                                  |                     |
         |                                  |                     |
+-----------------+                         |                     |
| Render Web      |  keyword CRUD, device   |                     |
| FastAPI app.py  |  registration           |                     |
+-----------------+                         |                     |
         |                                  |                     |
         | for each new match:              |                     |
         +-- sends email via Gmail SMTP --> raman.rounak@gmail.com|
         |                                  |                     |
         +-- sends push via FCM ----------> Android app on phones |
                                            +---------------------+
```
