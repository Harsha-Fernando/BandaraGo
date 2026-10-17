from django.urls import path
from . import views

app_name = 'attractions'
urlpatterns = [
    path('', views.place_list, name='list'),
    path('<slug:slug>/', views.place_detail, name='detail'),
]
