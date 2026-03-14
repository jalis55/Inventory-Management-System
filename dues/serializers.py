from rest_framework import serializers
from .models import (
    DuesSummary, CustomerDue, SupplierDue, 
    PaymentCollection, PaymentDisbursement,
    DueReminder, WriteOff
)
from customers.serializers import CustomerListSerializer
from suppliers.serializers import SupplierListSerializer
from sales.serializers import SalesOrderListSerializer
from purchases.serializers import PurchaseOrderListSerializer

class CustomerDueSerializer(serializers.ModelSerializer):
    customer_details = CustomerListSerializer(source='customer', read_only=True)
    sales_order_details = SalesOrderListSerializer(source='sales_order', read_only=True)
    
    class Meta:
        model = CustomerDue
        fields = '__all__'
        read_only_fields = ['id', 'days_overdue', 'created_at', 'updated_at']

class SupplierDueSerializer(serializers.ModelSerializer):
    supplier_details = SupplierListSerializer(source='supplier', read_only=True)
    purchase_order_details = PurchaseOrderListSerializer(source='purchase_order', read_only=True)
    
    class Meta:
        model = SupplierDue
        fields = '__all__'
        read_only_fields = ['id', 'days_overdue', 'created_at', 'updated_at']

class PaymentCollectionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer_due.customer.get_full_name', read_only=True)
    order_number = serializers.CharField(source='customer_due.sales_order.order_number', read_only=True)
    collected_by_name = serializers.CharField(source='collected_by.get_full_name', read_only=True)
    
    class Meta:
        model = PaymentCollection
        fields = '__all__'
        read_only_fields = ['id', 'collection_number', 'receipt_number', 'created_at']

class PaymentCollectionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCollection
        fields = ['customer_due', 'amount', 'payment_method', 'reference_number', 'transaction_id', 'notes']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
    
    def validate(self, data):
        customer_due = data['customer_due']
        if data['amount'] > customer_due.remaining_amount:
            raise serializers.ValidationError(
                f"Amount cannot exceed remaining due of {customer_due.remaining_amount}"
            )
        return data

class PaymentDisbursementSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier_due.supplier.company_name', read_only=True)
    po_number = serializers.CharField(source='supplier_due.purchase_order.po_number', read_only=True)
    disbursed_by_name = serializers.CharField(source='disbursed_by.get_full_name', read_only=True)
    
    class Meta:
        model = PaymentDisbursement
        fields = '__all__'
        read_only_fields = ['id', 'disbursement_number', 'voucher_number', 'created_at']

class PaymentDisbursementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDisbursement
        fields = ['supplier_due', 'amount', 'payment_method', 'reference_number', 
                 'transaction_id', 'cheque_number', 'notes']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
    
    def validate(self, data):
        supplier_due = data['supplier_due']
        if data['amount'] > supplier_due.remaining_amount:
            raise serializers.ValidationError(
                f"Amount cannot exceed remaining due of {supplier_due.remaining_amount}"
            )
        return data

class DueReminderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer_due.customer.get_full_name', read_only=True)
    supplier_name = serializers.CharField(source='supplier_due.supplier.company_name', read_only=True)
    
    class Meta:
        model = DueReminder
        fields = '__all__'
        read_only_fields = ['id', 'reminder_date', 'created_at']

class WriteOffSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer_due.customer.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = WriteOff
        fields = '__all__'
        read_only_fields = ['id', 'write_off_number', 'write_off_date', 'created_at']

class DuesSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DuesSummary
        fields = '__all__'

class CustomerAgingReportSerializer(serializers.Serializer):
    """Customer aging report serializer"""
    customer_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    total_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)
    current = serializers.DecimalField(max_digits=12, decimal_places=2)
    days_1_30 = serializers.DecimalField(max_digits=12, decimal_places=2)
    days_31_60 = serializers.DecimalField(max_digits=12, decimal_places=2)
    days_61_90 = serializers.DecimalField(max_digits=12, decimal_places=2)
    days_91_plus = serializers.DecimalField(max_digits=12, decimal_places=2)