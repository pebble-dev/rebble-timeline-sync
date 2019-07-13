from os import environ

domain_root = environ.get('DOMAIN_ROOT')
http_protocol = environ.get('HTTP_PROTOCOL', 'https')

config = {
    'SQLALCHEMY_DATABASE_URI': environ['DATABASE_URL'],
    'DOMAIN_ROOT': domain_root,
    'REBBLE_AUTH_URL': environ.get('REBBLE_AUTH_URL', f"{http_protocol}://auth.{domain_root}"),
    'APPSTORE_API_URL': environ.get('APPSTORE_API_URL', f"{http_protocol}://appstore-api.{domain_root}"),
}
