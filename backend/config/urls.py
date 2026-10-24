from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.schemas import get_schema_view
from rest_framework.permissions import AllowAny
urlpatterns=[path('admin/',admin.site.urls),path('api/schema/',get_schema_view(title='BrandProof API',version='1.0',public=True,permission_classes=[AllowAny])),path('api/v1/',include('app.urls')),path('',TemplateView.as_view(template_name='app/index.html'),name='frontend')]
