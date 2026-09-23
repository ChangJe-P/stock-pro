"""주몽 URL 라우팅. 기존 JSON API 경로와 root 화면을 같은 origin에서 제공한다."""

from django.urls import path

from trading import views

urlpatterns = [
    # 읽기 전용 대시보드
    path("", views.dashboard, name="dashboard"),
    # 상태 확인
    path("health", views.health, name="health"),
    # 시장 데이터(T-002 경로 유지)
    path("market-data/daily-prices/collect", views.market_data_collect, name="market_data_collect"),
    path("market-data/daily-prices", views.market_data_list, name="market_data_list"),
    # 가상계좌(T-003 경로 유지)
    path("virtual-account/initialize", views.virtual_account_initialize, name="virtual_account_initialize"),
    path("virtual-account/cash-ledger", views.virtual_account_cash_ledger, name="virtual_account_cash_ledger"),
    path("virtual-account", views.virtual_account_detail, name="virtual_account_detail"),
    # 가상 매수 주문(T-004 경로 유지)
    path("virtual-orders/<int:order_id>/execute", views.virtual_order_execute, name="virtual_order_execute"),
    path("virtual-orders", views.virtual_orders, name="virtual_orders"),
]
