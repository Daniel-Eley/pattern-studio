from django.urls import include, path
from processor.views import index

urlpatterns = [path('api/', include('processor.urls')), path('', index)]
