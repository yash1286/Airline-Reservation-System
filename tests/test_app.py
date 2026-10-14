import datetime
import importlib
import io
import re
import sys
from pathlib import Path
import mongomock
import pytest
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

@pytest.fixture
def app_module(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test-only-' * 6)
    monkeypatch.setenv('ADMIN_USERNAME', 'test-admin')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH', generate_password_hash('Test-admin-pass-42'))
    monkeypatch.setattr('pymongo.MongoClient', mongomock.MongoClient)
    sys.modules.pop('main', None)
    mod = importlib.import_module('main')
    mod.app.config.update(TESTING=True)
    return mod

@pytest.fixture
def client(app_module):
    return app_module.app.test_client()

def token(client, page='/customer_login'):
    text = client.get(page).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', text).group(1)

def login_as(client, mod, role='customer'):
    data = {'email':'test@example.com', 'password_hash':generate_password_hash('Test-password-42'), 'is_logged':True}
    coll = mod.mydatabase.customers if role=='customer' else mod.mydatabase.airlines
    identity = coll.insert_one(data).inserted_id
    with client.session_transaction() as sess:
        sess['role']=role
        sess[role+'_id']=str(identity)
    return identity

def fixture_flight(mod):
    db=mod.mydatabase
    airline=db.airlines.insert_one({'is_logged':True,'airline':'Demo'}).inserted_id
    a=db.locations.insert_one({'location':'Origin'}).inserted_id
    b=db.locations.insert_one({'location':'Destination'}).inserted_id
    origin=db.airports.insert_one({'location_id':a,'airport':'AAA'}).inserted_id
    destination=db.airports.insert_one({'location_id':b,'airport':'BBB'}).inserted_id
    plane=db.airplanes.insert_one({'airline_id':airline,'airplane_name':'Demo plane','image':'placeholder.svg',
        'economy_class_available_seats':'4','first_class_available_seats':'2','business_class_available_seats':'2'}).inserted_id
    departure=datetime.datetime.now()+datetime.timedelta(days=3)
    flight=db.schedules.insert_one({'airplane_id':plane,'departure_date_time':departure,
        'arrival_date_time':departure+datetime.timedelta(hours=2),'departure_date':departure.replace(hour=0,minute=0,second=0,microsecond=0),
        'source_airport_id':origin,'destination_airport_id':destination,'economic_class_price':'100',
        'business_class_price':'200','first_class_price':'300','flight_number':'D123','duration':'2 hours'}).inserted_id
    return flight, plane, airline

def book(client, mod, flight, seat=1):
    return client.post('/book_tickets3',data={'csrf_token':token(client), 'schedule_id':str(flight),
        'class_type':'economy_class','total_seats':'99999','total_price':'1',f'seat_number{seat}':str(seat),
        f'name{seat}':'Demo Passenger',f'age{seat}':'30',f'email{seat}':'demo@example.com'})

def test_public_pages_and_styles(client):
    for path in ['/', '/about','/customer_login','/airline_login','/admin_login','/customer_registration','/static/css/style.css']:
        assert client.get(path).status_code==200

def test_registration_hash_and_login(client, app_module):
    csrf=token(client)
    response=client.post('/customer_registration_action',data={'csrf_token':csrf,'email':'new@example.com',
        'phone':'123456789','password':'A-long-password-42','password2':'A-long-password-42'})
    assert response.status_code==200
    account=app_module.mydatabase.customers.find_one({'email':'new@example.com'})
    assert 'password' not in account
    assert check_password_hash(account['password_hash'],'A-long-password-42')
    assert client.post('/customer_login_action',data={'csrf_token':csrf,'email':'new@example.com','password':'A-long-password-42'}).status_code==302
    with client.session_transaction() as sess:
        assert sess['customer_id']==str(account['_id'])

def test_csrf_and_admin(client, app_module):
    assert client.post('/admin_login_action',data={'username':'test-admin','password':'Test-admin-pass-42'}).status_code==400
    assert client.post('/admin_login_action',data={'csrf_token':token(client), 'username':'test-admin','password':'Test-admin-pass-42'}).status_code==302
    assert client.get('/locations').status_code==200
    assert client.post('/logout',data={'csrf_token':token(client)}).status_code==302
    assert client.get('/locations').status_code==401

def test_legacy_password_rejected(client, app_module):
    app_module.mydatabase.customers.insert_one({'email':'legacy@example.com','password':'legacy-password'})
    client.post('/customer_login_action',data={'csrf_token':token(client),'email':'legacy@example.com','password':'legacy-password'})
    with client.session_transaction() as sess:
        assert 'role' not in sess

def test_roles_and_invalid_ids(client, app_module):
    assert client.get('/add_airplane').status_code==401
    login_as(client,app_module)
    assert client.get('/add_airplane').status_code==403
    assert client.get('/boarding_pass?booking_id=invalid').status_code==400
    assert client.get('/search_flights').status_code==200
    assert client.get('/search_flights?date=bad').status_code==400
    for path in ['/payments','/book_tickets3','/cancel','/cancel1','/logout']:
        assert client.get(path).status_code==405

def test_booking_payment_and_cancellation(client, app_module):
    login_as(client,app_module)
    flight,plane,airline=fixture_flight(app_module)
    db=app_module.mydatabase
    assert client.get(f'/book_ticket?schedule_id={flight}&class_type=economy_class&total_seats=4').status_code==200
    assert client.get(f'/book_tickets2?schedule_id={flight}&class_type=economy_class&total_seats=4&seat1=on').status_code==200
    response=book(client,app_module,flight)
    assert response.status_code==200
    assert b'name="card_number"' not in response.data and b'name="cvv"' not in response.data
    booking=db.bookings.find_one()
    assert booking['total_price']==100
    assert book(client,app_module,flight).status_code==409
    payload={'csrf_token':token(client),'booking_id':str(booking['_id']),'total_price':'1','card_number':'discard-me','cvv':'discard-me'}
    assert client.post('/payments',data=payload).status_code==200
    assert client.post('/payments',data=payload).status_code==200
    receipt=db.payments.find_one()
    assert receipt['amount']==100 and db.payments.count_documents({})==1
    assert not {'card_number','cvv','card_holder_name','expiry_date'} & receipt.keys()
    assert client.get('/bookings').status_code==200
    assert client.get(f'/boarding_pass?booking_id={booking["_id"]}').status_code==200
    assert client.get(f'/view_payments?booking_id={booking["_id"]}').status_code==200
    assert client.post('/cancel',data=payload).status_code==302
    assert db.schedules.find_one({'_id':flight})['reserved_seats']==[]
    assert db.boarding_pass.find_one()['status']=='Cancelled'

def test_record_ownership(client, app_module):
    flight,_,_=fixture_flight(app_module)
    login_as(client,app_module)
    assert book(client,app_module,flight).status_code==200
    booking=app_module.mydatabase.bookings.find_one()
    second=app_module.app.test_client()
    login_as(second,app_module)
    for endpoint in ['/view_payments','/boarding_pass']:
        assert second.get(endpoint+'?booking_id='+str(booking['_id'])).status_code==403
    for endpoint in ['/payments','/cancel']:
        assert second.post(endpoint,data={'csrf_token':token(second),'booking_id':str(booking['_id'])}).status_code==403
    passenger=app_module.mydatabase.boarding_pass.find_one()
    assert second.post('/cancel1',data={'csrf_token':token(second),'boarding_pass_id':str(passenger['_id'])}).status_code==403

def test_airline_ownership_and_upload(client, app_module):
    _,plane,_=fixture_flight(app_module)
    login_as(client,app_module,'airline')
    assert client.get('/add_schedule?airplane_id='+str(plane)).status_code==403
    data={'csrf_token':token(client),'airplane_name':'Demo','economy_class_available_seats':'4',
        'first_class_available_seats':'2','business_class_available_seats':'2',
        'image':(io.BytesIO(b'<script>bad</script>'),'../../bad.png')}
    assert client.post('/add_airplane_action',data=data).status_code==400
    data.pop('image')
    assert client.post('/add_airplane_action',data=data).status_code==200
    assert app_module.mydatabase.airplanes.find_one({'airplane_name':'Demo'})['image']=='placeholder.svg'

def test_all_templates_parse(app_module):
    for path in Path(__file__).resolve().parents[1].glob('*.html'):
        app_module.app.jinja_env.get_template(path.name)

def test_airline_password_workflow(client, app_module):
    db=app_module.mydatabase
    client.post('/admin_login_action',data={'csrf_token':token(client),'username':'test-admin','password':'Test-admin-pass-42'})
    assert client.post('/airline_registration_action',data={'csrf_token':token(client),'email':'air@example.com','phone':'4567','airline':'Demo Air','password':'Temporary-pass-42'}).status_code==302
    account=db.airlines.find_one({'email':'air@example.com'})
    assert 'password' not in account
    client.post('/logout',data={'csrf_token':token(client)})
    assert client.post('/airline_login_action',data={'csrf_token':token(client),'email':'air@example.com','password':'Temporary-pass-42'}).status_code==200
    assert client.get('/add_airplane').status_code==403
    assert client.post('/change_airline_password_action',data={'csrf_token':token(client),'password':'Replacement-pass-42','password2':'Replacement-pass-42'}).status_code==302
    assert client.get('/add_airplane').status_code==200
    account=db.airlines.find_one({'email':'air@example.com'})
    assert check_password_hash(account['password_hash'],'Replacement-pass-42')

def test_partial_cancel_does_not_release_rebooked_seat(client, app_module):
    login_as(client,app_module)
    flight,_,_=fixture_flight(app_module)
    assert book(client,app_module,flight).status_code==200
    db=app_module.mydatabase
    old=db.bookings.find_one()
    passenger=db.boarding_pass.find_one()
    payload={'csrf_token':token(client),'boarding_pass_id':str(passenger['_id'])}
    assert client.post('/cancel1',data=payload).status_code==200
    assert book(client,app_module,flight).status_code==200
    assert client.post('/cancel1',data=payload).status_code==200
    client.post('/cancel',data={'csrf_token':token(client),'booking_id':str(old['_id'])})
    assert db.schedules.find_one({'_id':flight})['reserved_seats']==['economy_class:1']
