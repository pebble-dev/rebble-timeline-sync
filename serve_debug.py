from os import environ
from apscheduler.schedulers.background import BackgroundScheduler

from timeline_sync import app, nightly_maintenance

app.run(environ.get("HOST", "127.0.0.1"), environ.get("PORT", 5000), debug=True)

# Use BackgroundScheduler in Docker mode; on prod, we call in directly from Zappa.
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(timeline_sync.nightly_maintenance, 'cron', [], hour=4, minute=0)  # Runs every day at 4 AM
scheduler.start()
