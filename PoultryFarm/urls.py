"""
URL configuration for PoultryFarm project.
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.generic import TemplateView
from FarmApplication import views as farm_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html', success_url='/accounts/password_change/done/'), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    path('accounts/password_reset/', farm_views.password_reset_with_old_password, name='password_reset'),
    path('accounts/password_reset/done/', TemplateView.as_view(template_name='registration/password_reset_with_old_password_done.html'), name='password_reset_done'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('FarmApplication.urls')),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

