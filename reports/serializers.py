from rest_framework import serializers
from .models import SavedReport, ReportGeneration, DashboardWidget

class SavedReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = SavedReport
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_generated']

class ReportGenerationSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    
    class Meta:
        model = ReportGeneration
        fields = '__all__'
        read_only_fields = ['id', 'started_at', 'completed_at', 'execution_time']

class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


# Report Data Serializers (for various report types)
class DateRangeSerializer(serializers.Serializer):
    """Date range for reports"""
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date must be before end date")
        return data


class SalesReportSerializer(serializers.Serializer):
    """Sales report parameters"""
    date_range = DateRangeSerializer()
    group_by = serializers.ChoiceField(choices=['day', 'week', 'month', 'quarter', 'year'], default='day')
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    sales_person_id = serializers.UUIDField(required=False, allow_null=True)
    include_tax = serializers.BooleanField(default=True)
    include_discounts = serializers.BooleanField(default=True)


class PurchaseReportSerializer(serializers.Serializer):
    """Purchase report parameters"""
    date_range = DateRangeSerializer()
    group_by = serializers.ChoiceField(choices=['day', 'week', 'month', 'quarter', 'year'], default='month')
    supplier_id = serializers.UUIDField(required=False, allow_null=True)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    order_status = serializers.MultipleChoiceField(
        choices=['draft', 'approved', 'ordered', 'received', 'cancelled'],
        required=False
    )


class InventoryReportSerializer(serializers.Serializer):
    """Inventory report parameters"""
    warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    include_zero_stock = serializers.BooleanField(default=False)
    low_stock_only = serializers.BooleanField(default=False)
    expiring_only = serializers.BooleanField(default=False)
    expiry_days = serializers.IntegerField(default=30, min_value=1)


class CustomerReportSerializer(serializers.Serializer):
    """Customer report parameters"""
    date_range = DateRangeSerializer(required=False)
    customer_type = serializers.ChoiceField(
        choices=['retail', 'wholesale', 'corporate', 'vip', 'all'],
        default='all'
    )
    loyalty_tier = serializers.ChoiceField(
        choices=['bronze', 'silver', 'gold', 'platinum', 'diamond', 'all'],
        default='all'
    )
    top_n = serializers.IntegerField(default=10, min_value=1, max_value=100)
    sort_by = serializers.ChoiceField(
        choices=['total_purchases', 'order_count', 'loyalty_points', 'outstanding'],
        default='total_purchases'
    )


class FinancialReportSerializer(serializers.Serializer):
    """Financial report parameters"""
    date_range = DateRangeSerializer()
    report_type = serializers.ChoiceField(
        choices=['profit_loss', 'cash_flow', 'dues_aging', 'revenue_breakdown'],
        default='profit_loss'
    )
    include_tax = serializers.BooleanField(default=True)


class DuesReportSerializer(serializers.Serializer):
    """Dues/Aging report parameters"""
    as_of_date = serializers.DateField(required=False)
    type = serializers.ChoiceField(choices=['receivables', 'payables', 'both'], default='both')
    aging_buckets = serializers.ListField(
        child=serializers.IntegerField(),
        default=[0, 30, 60, 90]
    )
