from django.urls import path
from . import views

app_name = 'planner'
urlpatterns = [
    path('', views.plan_detail, name='detail'),
    path('download/', views.download_pdf, name='download_pdf'),
    path('add/<int:place_id>/', views.add, name='add'),
    path('reorder/<int:place_id>/', views.reorder, name='reorder'),
    path('remove/<int:place_id>/confirm/', views.confirm_remove, name='confirm_remove'),
    path('remove/<int:place_id>/', views.remove, name='remove'),
    path('clear/confirm/', views.confirm_clear, name='confirm_clear'),
    path('clear/', views.clear, name='clear'),
]
