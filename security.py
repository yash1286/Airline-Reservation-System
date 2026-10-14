"""Authentication, authorization and input boundaries for the local demo."""
import datetime
import os
import uuid
from pathlib import Path
from bson import ObjectId
from bson.errors import InvalidId
from flask import abort, request, session
from PIL import Image, UnidentifiedImageError
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash


def password_hash(value):
    if not value or not 12 <= len(value) <= 128:
        abort(400, 'Use a password of 12–128 characters')
    return generate_password_hash(value)


def verify_password(stored, value):
    if not stored or not value or len(value) > 128:
        return False
    if not stored.startswith(('scrypt:', 'pbkdf2:')):
        return False  # Legacy plaintext accounts require an explicit reset.
    try:
        return check_password_hash(stored, value)
    except (ValueError, TypeError):
        return False


def airplane_access(db, airplane_id):
    plane = db.airplanes.find_one({'_id': ObjectId(airplane_id)})
    if not plane:
        abort(404)
    if session.get('role') != 'airline' or str(plane['airline_id']) != session.get('airline_id'):
        abort(403)
    return plane


def schedule_access(db, schedule_id):
    flight = db.schedules.find_one({'_id': ObjectId(schedule_id)})
    if not flight:
        abort(404)
    airplane_access(db, flight['airplane_id'])
    return flight


def booking_access(db, booking_id, customer_only=False):
    booking = db.bookings.find_one({'_id': ObjectId(booking_id)})
    if not booking:
        abort(404)
    if session.get('role') == 'customer':
        if str(booking['customer_id']) != session.get('customer_id'):
            abort(403)
    elif session.get('role') == 'airline' and not customer_only:
        schedule_access(db, booking['schedule_id'])
    else:
        abort(403)
    return booking


def safe_upload(upload, directory):
    if not upload or not upload.filename:
        return 'placeholder.svg'
    try:
        with Image.open(upload.stream) as img:
            if img.format not in {'PNG', 'JPEG'} or img.width * img.height > 16_000_000:
                abort(400, 'Upload a PNG or JPEG below 16 megapixels')
            img.load()
            filename = uuid.uuid4().hex + '.png'
            img.convert('RGB').save(Path(directory) / filename, format='PNG')
            return filename
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        abort(400, 'Invalid image')


def configure_security(app, db):
    secret = os.environ.get('SECRET_KEY', '')
    if len(secret) < 32:
        raise RuntimeError('Set SECRET_KEY to at least 32 random characters. See README.md.')
    app.config.update(SECRET_KEY=secret, MAX_CONTENT_LENGTH=4 * 1024 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1')
    public = {'index', 'about', 'admin', 'admin_login_action', 'customer_login',
              'customer_login_action', 'customer_registration', 'customer_registration_action',
              'airline_login', 'airline_login_action', 'static'}
    admin = {'admin_home', 'airline_registration', 'airline_registration_action',
             'locations', 'locations_action', 'airports', 'airport_action', 'edit_location', 'edit_locations_action'}
    airline = {'airline_home', 'change_airline_password_action', 'add_airplane',
               'add_airplane_action', 'add_schedule', 'schedules_action', 'view_schedule'}
    customer = {'customer_home', 'search_flights', 'book_ticket', 'book_tickets2',
                'book_tickets3', 'payments', 'cancel', 'cancel1'}
    shared = {'bookings', 'boarding_pass', 'view_payments', 'logout'}

    @app.before_request
    def protect():
        endpoint = request.endpoint
        if endpoint is None:
            return
        values = request.form if request.method == 'POST' else request.args
        for key, value in values.items():
            if key.endswith('_id') and value and not ObjectId.is_valid(value):
                abort(400, 'Invalid identifier')
        if endpoint in {'customer_registration_action', 'airline_registration_action'}:
            if not values.get('email', '').strip() or '@' not in values.get('email', '') or not values.get('phone', '').strip():
                abort(400, 'Email and phone are required')
        if endpoint == 'schedules_action':
            for key in ['arrival_date_time', 'departure_date_time']:
                if not values.get(key):
                    abort(400, 'Flight dates are required')
                datetime.datetime.strptime(values[key], '%Y-%m-%dT%H:%M')
        if endpoint in public:
            return
        role = session.get('role')
        if not role:
            abort(401)
        allowed = ((endpoint in admin and role == 'admin') or
                   (endpoint in airline and role == 'airline') or
                   (endpoint in customer and role == 'customer') or
                   (endpoint in shared and role in {'customer', 'airline', 'admin'}))
        if not allowed:
            abort(403)
        if role in {'customer', 'airline'}:
            collection = db.customers if role == 'customer' else db.airlines
            identity = session.get(role + '_id')
            if not identity or not ObjectId.is_valid(identity) or not collection.find_one({'_id': ObjectId(identity)}):
                session.clear()
                abort(401)
        if role == 'airline':
            account = db.airlines.find_one({'_id': ObjectId(session['airline_id'])})
            if not account.get('is_logged') and endpoint not in {'change_airline_password_action', 'logout'}:
                abort(403, 'Complete the initial password change')
        if endpoint in {'add_schedule', 'schedules_action', 'view_schedule'}:
            airplane_access(db, values.get('airplane_id'))
        if endpoint == 'bookings' and role != 'customer':
            schedule_access(db, values.get('schedule_id'))
        if endpoint in {'boarding_pass', 'view_payments'}:
            booking_access(db, values.get('booking_id'))
        if endpoint == 'airport_action' and not db.locations.find_one({'_id': ObjectId(values.get('location_id'))}):
            abort(400, 'Unknown location')
        if endpoint in {'edit_location', 'edit_locations_action'} and not db.locations.find_one({'_id': ObjectId(values.get('location_id'))}):
            abort(404)
        if endpoint == 'add_airplane_action':
            for key in ['economy_class_available_seats', 'business_class_available_seats', 'first_class_available_seats']:
                number = values.get(key, '')
                if not number.isdigit() or not 0 <= int(number) <= 500:
                    abort(400, 'Seat capacity must be between 0 and 500')
        if endpoint == 'schedules_action':
            for key in ['business_class_price', 'economic_class_price', 'first_class_price']:
                number = values.get(key, '')
                if not number.isdigit() or not 0 <= int(number) <= 100000:
                    abort(400, 'Invalid price')
            for key in ['source_airport_id', 'destination_airport_id']:
                if not db.airports.find_one({'_id': ObjectId(values.get(key))}):
                    abort(400, 'Unknown airport')
        if endpoint in {'book_ticket', 'book_tickets2'}:
            flight = db.schedules.find_one({'_id': ObjectId(values.get('schedule_id'))})
            if not flight or flight['departure_date_time'] <= datetime.datetime.now():
                abort(400, 'Flight unavailable')
            plane = db.airplanes.find_one({'_id': flight['airplane_id']})
            field = {'first_class':'first_class_available_seats', 'business_class':'business_class_available_seats',
                     'economy_class':'economy_class_available_seats'}.get(values.get('class_type'))
            if not plane or not field or values.get('total_seats') != str(plane[field]):
                abort(400, 'Invalid cabin capacity')

    @app.errorhandler(DuplicateKeyError)
    def duplicate_record(error):
        return 'A record with this unique value already exists', 409

    @app.errorhandler(InvalidId)
    def invalid_id(error):
        return 'Invalid identifier', 400

    @app.errorhandler(ValueError)
    def invalid_value(error):
        return 'Invalid input value', 400

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response
