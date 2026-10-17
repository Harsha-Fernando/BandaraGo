from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from attractions import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('help/', TemplateView.as_view(template_name='help.html'), name='help'),
    path('planner/', include('planner.urls')),
    path('', views.place_list, name='home'),
    path('attractions/', include('attractions.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
