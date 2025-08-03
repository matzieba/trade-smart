from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from trade_smart.poractive_proposition.views import InvestmentGoalViewSet, propose

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("advice/", InvestmentGoalViewSet.as_view({"post"}), name="advice"),
    path("propose/", propose, name="propose"),
]
