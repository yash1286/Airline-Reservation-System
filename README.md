# Airline Reservation System

A local Python and MongoDB demonstration of airline scheduling, passenger bookings, and simulated payment receipts. It includes admin, airline, and customer workflows with role and record-ownership checks.

**This is a portfolio demo using synthetic data. No real payments or refunds are processed.**

## Stack and architecture

Python 3.12, Flask, Jinja templates, PyMongo, MongoDB, Flask-WTF, and Pillow.

Browser forms reach Flask routes in `main.py`. `security.py` applies authentication, role checks, ownership checks, input boundaries, and image validation. Routes read and write MongoDB collections and render the root-level HTML templates. CSS and demo image assets are included under `static/`.

## Local setup

Install Python 3.12 and run a local MongoDB service. Use a fresh `airline_demo` database for this version.

```bash
git clone https://github.com/yash1286/Airline-Reservation-System.git
cd Airline-Reservation-System
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux, or `.venv\Scripts\activate` in Windows Command Prompt, then install:

```bash
python -m pip install -r requirements.txt
```

Set environment variables in your terminal. `.env.example` documents the settings; it is a reference file and is not loaded automatically.

macOS/Linux:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_USERNAME="demo-admin"
export ADMIN_PASSWORD_HASH="$(python manage.py hash-password)"
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DATABASE="airline_demo"
python manage.py init-db
python main.py
```

PowerShell (activate with `.venv\Scripts\Activate.ps1`):

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:ADMIN_USERNAME = "demo-admin"
$env:ADMIN_PASSWORD_HASH = python manage.py hash-password
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DATABASE = "airline_demo"
python manage.py init-db
python main.py
```

Open `http://127.0.0.1:5000`. Password setup prompts locally without echoing the password. Keep your generated secret stable between restarts if you want existing sessions to remain valid. Never commit environment secrets.

## Walk through the demo

1. Log in as the configured admin. Create two locations, two airports, and an airline account with a temporary password of at least 12 characters.
2. Log in as the airline and complete the initial password change. Add an aircraft and a future flight schedule. Aircraft images are optional; a bundled placeholder is used when omitted.
3. Register a synthetic customer account. Search the flight, select seats, and enter synthetic passenger details.
4. Confirm the simulated booking. The server calculates the price from the stored schedule. No card input is shown or persisted.
5. Review bookings, boarding passes, and demo receipts. Cancellation releases the applicable seat holds and processes no real refund.

## Repairs included

- Password hashes replace plaintext credential storage. Legacy plaintext accounts cannot log in until explicitly reset.
- Admin credentials and the session secret come from environment variables; there is no default admin password.
- CSRF tokens protect POST forms. Booking creation, confirmation, cancellations, and logout are POST-only.
- Role checks and record ownership restrict airline and customer access. Logout clears the session.
- Card-entry and card-display fields have been removed. Confirmation records contain only demo receipt metadata.
- Booking prices and seat capacity are validated against database records. An atomic schedule update prevents two active requests from claiming the same seat.
- Root templates are configured explicitly, styling is bundled, image uploads are decoded and re-encoded under random filenames, and deprecated PyMongo insert calls are replaced.
- Missing/invalid search dates are handled. Development startup is guarded and debug mode is off.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests use Flask's test client and an in-memory MongoDB substitute. They cover registration and login, legacy credential rejection, CSRF, role/ownership checks, booking and confirmation, duplicate seat claims, cancellation, upload validation, and template parsing. They do not substitute for browser testing or integration tests against a running MongoDB server.

## Existing data and remaining limits

Use a fresh demo database: legacy bookings do not have the new seat-claim state. No automatic destructive migration runs. Back up any existing database before resetting or migrating records. Old stored card fields are not automatically erased by this code update; clean those records separately under your data-retention process.

An operator can explicitly reset a legacy account password:

```bash
python manage.py reset-password --role customer --email demo@example.com
```

The application remains a local demo. Pending seat holds have no automatic expiry. Booking, passenger, and receipt writes span multiple documents without transactions, so crashes and concurrent cancellation/confirmation need further handling before production use. Further work includes rate limiting, broader business-rule validation, transactional recovery, deployment hardening, and real MongoDB/browser integration testing. No real payment gateway is included.
