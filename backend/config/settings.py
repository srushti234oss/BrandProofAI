import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
    load_dotenv(BASE_DIR.parent / '.env')
except ImportError:
    pass
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
if not DEBUG and (len(SECRET_KEY)<32 or 'replace' in SECRET_KEY.lower()):
    raise RuntimeError('Set DJANGO_SECRET_KEY to a strong random value (32+ characters) before disabling debug mode.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')
if not DEBUG and '*' in ALLOWED_HOSTS:
    raise RuntimeError('Set DJANGO_ALLOWED_HOSTS explicitly before disabling debug mode.')
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','app']
MIDDLEWARE = ['config.cors.SimpleCorsMiddleware','django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
try:
    import whitenoise.middleware
    MIDDLEWARE.insert(2,'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass  # Local API development can run without the optional production static-file server.
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
if os.getenv('DATABASE_URL'):
    import urllib.parse
    u=urllib.parse.urlparse(os.environ['DATABASE_URL'])
    params=urllib.parse.parse_qs(u.query)
    database_options={'sslmode':params.get('sslmode',['prefer'])[0]} if params.get('sslmode') else {}
    DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':urllib.parse.unquote(u.path.lstrip('/')),'USER':urllib.parse.unquote(u.username or ''),'PASSWORD':urllib.parse.unquote(u.password or ''),'HOST':u.hostname,'PORT':u.port or 5432,'CONN_MAX_AGE':60,'CONN_HEALTH_CHECKS':True,'OPTIONS':database_options}}
else: DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
if os.getenv('EMAIL_HOST'):
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST=os.environ['EMAIL_HOST']; EMAIL_PORT=int(os.getenv('EMAIL_PORT','587'))
    EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER',''); EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD','')
    EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS','true').lower()=='true'
    EMAIL_USE_SSL=os.getenv('EMAIL_USE_SSL','false').lower()=='true'
    DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL',EMAIL_HOST_USER or 'brandproof@localhost')
PUBLIC_APP_URL=os.getenv('PUBLIC_APP_URL','http://localhost:5173').rstrip('/')
if os.getenv('DJANGO_STORAGE_BACKEND','local').lower()=='s3':
    STORAGES={'default':{'BACKEND':'storages.backends.s3.S3Storage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
    AWS_STORAGE_BUCKET_NAME=os.environ['AWS_STORAGE_BUCKET_NAME']
    AWS_S3_REGION_NAME=os.getenv('AWS_S3_REGION_NAME','') or None
    AWS_S3_ENDPOINT_URL=os.getenv('AWS_S3_ENDPOINT_URL','') or None
    AWS_S3_FILE_OVERWRITE=False
    AWS_DEFAULT_ACL=None
    AWS_QUERYSTRING_AUTH=True
    AWS_QUERYSTRING_EXPIRE=int(os.getenv('AWS_QUERYSTRING_EXPIRE','300'))
    AWS_S3_OBJECT_PARAMETERS={'ServerSideEncryption':os.getenv('AWS_S3_SERVER_SIDE_ENCRYPTION','AES256')}
    if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
        AWS_ACCESS_KEY_ID=os.environ['AWS_ACCESS_KEY_ID']; AWS_SECRET_ACCESS_KEY=os.environ['AWS_SECRET_ACCESS_KEY']
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':8}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='UTC'; USE_I18N=True; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[BASE_DIR/'static']; DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
SESSION_COOKIE_SAMESITE='Lax'; CSRF_COOKIE_SAMESITE='Lax'
SECURE_CONTENT_TYPE_NOSNIFF=True; X_FRAME_OPTIONS='DENY'
if not DEBUG:
    SESSION_COOKIE_SECURE=True
    CSRF_COOKIE_SECURE=True
    SECURE_SSL_REDIRECT=True
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
MEDIA_ROOT=BASE_DIR/'media'; MEDIA_URL='/media/'
CORS_ALLOWED_ORIGINS=os.getenv('CORS_ALLOWED_ORIGINS','http://localhost:5173').split(',')
CSRF_TRUSTED_ORIGINS=os.getenv('CSRF_TRUSTED_ORIGINS','http://localhost:5173').split(',')
FILE_UPLOAD_MAX_MEMORY_SIZE=5*1024*1024
DATA_UPLOAD_MAX_MEMORY_SIZE=25*1024*1024
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication','rest_framework.authentication.BasicAuthentication'],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.AnonRateThrottle','rest_framework.throttling.UserRateThrottle'],'DEFAULT_THROTTLE_RATES':{'anon':'20/min','user':'120/min'}}
