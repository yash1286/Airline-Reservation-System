"""Local operator commands. Run only against a backed-up demo database."""
import argparse
import getpass
from werkzeug.security import generate_password_hash

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['hash-password','reset-password','init-db'])
parser.add_argument('--role', choices=['customer','airline'])
parser.add_argument('--email')
args = parser.parse_args()
if args.command == 'hash-password':
    value=getpass.getpass('Password (12–128 characters): ')
    if not 12 <= len(value) <= 128:
        parser.error('Password must be 12–128 characters')
    print(generate_password_hash(value))
else:
    from main import mydatabase
    if args.command == 'init-db':
        # Existing duplicate records cause an explicit error rather than data loss.
        for name in ['customers','airlines']:
            mydatabase[name].create_index('email', unique=True)
            mydatabase[name].create_index('phone', unique=True)
        mydatabase.payments.create_index('booking_id', unique=True)
        print('Demo indexes created.')
    else:
        if not args.role or not args.email:
            parser.error('reset-password requires --role and --email')
        value=getpass.getpass('New password (12–128 characters): ')
        if not 12 <= len(value) <= 128:
            parser.error('Password must be 12–128 characters')
        collection=mydatabase.customers if args.role=='customer' else mydatabase.airlines
        result=collection.update_one({'email':args.email}, {'$set':{'password_hash':generate_password_hash(value)},'$unset':{'password':''}})
        print('Password reset.' if result.matched_count else 'No matching account; nothing changed.')
