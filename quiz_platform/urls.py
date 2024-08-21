from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('quiz.urls')),  # Assuming you have an api_urls.py for API endpoints
    path('', include('quiz.urls')),

]

