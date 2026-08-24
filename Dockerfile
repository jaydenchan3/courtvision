# CourtVision: one image that can both serve the app and run the full test
# suite, including the Selenium end-to-end layer. Docker is an added option,
# never the only way to run this -- the plain python workflow is unchanged.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Chromium and its driver come from apt rather than being fetched at test time.
# Selenium Manager would otherwise download a driver on first run, which needs
# network access inside the container and makes the image's behaviour depend on
# when it is run. Pinning both to the distro package keeps browser and driver
# versions matched by construction -- the version-mismatch failure that bites
# most Selenium setups cannot happen here.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# conftest picks these up when set and falls back to Selenium Manager when they
# are not, so the same test code runs in the container and on a laptop.
ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver

# A container gets less CPU than a laptop and Chrome is the slow part. This
# changes only the budget a wait is allowed before giving up, not the waits
# themselves -- a wait that expires while the app is still working reports a
# failure that is not there. Waits still return the instant their condition
# holds, so a larger budget costs nothing when things are fast.
ENV SELENIUM_WAIT_TIMEOUT=30

# The spinner window has to stay observable in a slower environment.
# driver.get() returns at the load event, but dashboard.js starts its fetch at
# DOMContentLoaded, which is earlier. If more than DASHBOARD_DELAY_MS elapses
# between the two -- easy on a contended container -- the fetch has already
# resolved and the spinner is gone before a test can see it. Widening the delay
# widens the window. The app is unchanged; this is the same knob the app
# already exposes.
ENV DASHBOARD_DELAY_MS=1500

WORKDIR /app

# Requirements are copied and installed BEFORE the application code, on purpose.
# Docker caches each layer and invalidates everything after the first changed
# one. Copying the whole tree first would mean any edit to a template or a test
# re-ran pip install; this way a code change reuses the cached dependency layer
# and rebuilds take seconds.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seeding happens at container start, NOT at build time. seed.py dates its three
# games to the current US/Eastern date, so a database baked into the image would
# be stale the next day and the dashboard's "games tonight" assertions would
# fail for reasons unrelated to the code.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 5000
CMD ["python", "-m", "flask", "--app", "app:create_app", "run", "--host", "0.0.0.0", "--port", "5000"]
