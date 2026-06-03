import atexit
import logging
import os
import threading

from flask import Flask, jsonify, render_template
from apscheduler.schedulers.background import BackgroundScheduler

from database import init_db, get_latest_data
from scraper import run_scraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

SCRAPE_INTERVAL_HOURS = int(os.environ.get('SCRAPE_INTERVAL_HOURS', 6))


@app.route('/')
def dashboard():
    data = get_latest_data()
    return render_template('dashboard.html', **data, interval_hours=SCRAPE_INTERVAL_HOURS)


@app.route('/api/data')
def api_data():
    return jsonify(get_latest_data())


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


def _run_scraper_thread():
    t = threading.Thread(target=run_scraper, daemon=True)
    t.start()


if __name__ == '__main__':
    init_db()

    # Run first scrape in background so the web server starts immediately
    log.info('Scheduling initial scrape...')
    _run_scraper_thread()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_scraper_thread,
        trigger='interval',
        hours=SCRAPE_INTERVAL_HOURS,
        id='scraper',
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))

    port = int(os.environ.get('PORT', 5000))
    log.info('Starting web server on port %s', port)
    app.run(host='0.0.0.0', port=port, use_reloader=False)
