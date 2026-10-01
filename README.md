# Airline Reservation System

A Python web application prototype for airline administration, flight scheduling, customer registration, seat selection, and booking records. The source uses Flask for HTTP routes and templates, and MongoDB for persistence.

**Status:** learning/demo source. The current checkout needs setup repairs and security work before a complete local demonstration or deployment.

## Technology

- Python and Flask
- MongoDB with PyMongo
- Jinja HTML templates and browser forms

## Implemented workflows

- Administration of locations, airports, and airlines
- Airline aircraft and schedule management
- Customer registration and login
- Flight search, seat selection, and booking
- Boarding-pass views and cancellation records
- A simulated payment-record workflow; no payment gateway integration is present

## Code and data structure

`main.py` contains the routes, database access, and application startup. HTML files currently sit in the repository root.

The `airline` database contains collections for locations, airports, airlines, airplanes, schedules, customers, bookings, boarding passes, and payments. Documents reference related records through MongoDB ObjectIds.

A browser request is handled by a Flask route, which reads or writes MongoDB records and renders a Jinja template.

## Local setup prerequisites

The repository is not yet a one-command runnable package. Before attempting a demo:

1. Create a Python virtual environment and install Flask and PyMongo. The `bson` import is supplied by PyMongo.
2. Run a local MongoDB service at the URI configured in `main.py`.
3. Move the root HTML files into a `templates/` directory, or explicitly configure Flask's template directory.
4. Restore the referenced static assets and create `static/profiles/` for local demo uploads.
5. Remove the unused `idlelib` import if IDLE/Tk is unavailable in the environment.
6. Replace legacy collection `insert()` calls with supported PyMongo operations, and validate the application with the selected dependency versions.

After those repairs, `python main.py` starts the development server. Use synthetic data only. An end-to-end run has not been verified.

## Known limitations

- Authentication uses plaintext passwords and hard-coded demo authentication/session values.
- Role and record-ownership checks need to be enforced consistently across routes.
- Logout currently redirects without clearing the session.
- The payment route stores submitted card fields, including CVV. Remove that behavior before any real use; the demo must never receive actual payment details.
- Booking mutations need request validation, CSRF protection, and concurrency controls to prevent duplicate seat bookings.
- Debug mode is enabled in the source.
- Static assets, a dependency lock file, automated tests, and a reproducible setup are not included.

## Data engineering extension ideas

Future work could turn synthetic booking events into an analytics demonstration: ingest events, validate schemas, model booking and flight facts, and calculate occupancy and cancellation metrics. These extensions are ideas and are not implemented in this repository.
