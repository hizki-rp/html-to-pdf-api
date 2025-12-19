from django.urls import path
from .views import convert_html

urlpatterns = [
    path('convert', convert_html, name='convert_html'),
]
