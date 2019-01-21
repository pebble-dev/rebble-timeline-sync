from os import environ

domain_root = environ.get('DOMAIN_ROOT')

config = {
    'SQLALCHEMY_DATABASE_URI': environ['DATABASE_URL'],
    'DOMAIN_ROOT': domain_root,
    'REBBLE_AUTH_URL': environ.get('REBBLE_AUTH_URL', f"https://auth.{domain_root}"),
    'APPSTORE_API_URL': environ.get('APPSTORE_API_URL', f"http://appstore-api.{domain_root}"),
}
