from os import environ

domain_root = environ.get('DOMAIN_ROOT')
http_protocol = environ.get('HTTP_PROTOCOL', 'https')

config = {
    'SQLALCHEMY_DATABASE_URI': environ['DATABASE_URL'],
    'DOMAIN_ROOT': domain_root,
    'REBBLE_AUTH_URL': environ.get('REBBLE_AUTH_URL', f"{http_protocol}://auth.{domain_root}"),
    'APPSTORE_API_URL': environ.get('APPSTORE_API_URL', f"{http_protocol}://appstore-api.{domain_root}"),
    'SECRET_KEY': environ.get('SECRET_KEY'),
    'FIREBASE_PROJECT_ID': environ.get('FIREBASE_PROJECT_ID'),
    'FIREBASE_CLIENT_EMAIL': environ.get('FIREBASE_CLIENT_EMAIL'),
    'FIREBASE_PRIVATE_KEY': environ.get('FIREBASE_PRIVATE_KEY'),
    'HONEYCOMB_KEY': environ.get('HONEYCOMB_KEY', None),
}
