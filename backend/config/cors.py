class SimpleCorsMiddleware:
    def __init__(self, get_response): self.get_response=get_response
    def __call__(self, request):
        if request.method=='OPTIONS':
            from django.http import HttpResponse
            response=HttpResponse(status=204)
        else: response=self.get_response(request)
        origin=request.headers.get('Origin','')
        allowed=__import__('os').getenv('CORS_ALLOWED_ORIGINS','http://localhost:5173').split(',')
        if origin in allowed:
            response['Access-Control-Allow-Origin']=origin
            response['Access-Control-Allow-Credentials']='true'
            response['Access-Control-Allow-Headers']='Content-Type, X-CSRFToken'
            response['Access-Control-Allow-Methods']='GET, POST, PATCH, DELETE, OPTIONS'
            response['Access-Control-Max-Age']='600'
            response['Vary']='Origin'
        return response
