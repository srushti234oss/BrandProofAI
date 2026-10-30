from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.shortcuts import render
from rest_framework.schemas import get_schema_view
from rest_framework.permissions import AllowAny
def frontend(request):
    return render(request,'app/index.html',{
        'demo_username':settings.DEMO_USERNAME,
        'demo_password':settings.DEMO_PASSWORD,
    })

urlpatterns=[path('admin/',admin.site.urls),path('api/schema/',get_schema_view(title='BrandProof API',version='1.0',public=True,permission_classes=[AllowAny])),path('api/v1/',include('app.urls')),path('',frontend,name='frontend')]
