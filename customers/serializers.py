from rest_framework import serializers
from .models import (
    Customer, CustomerAddress, CustomerContact, 
    CustomerInteraction, CustomerLoyalty, CustomerDocument,
    CustomerPayment
)

class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'created_at', 'updated_at']

class CustomerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerContact
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'created_at', 'updated_at']

class CustomerInteractionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = CustomerInteraction
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class CustomerLoyaltySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerLoyalty
        fields = '__all__'
        read_only_fields = ['id', 'membership_date', 'last_activity_date']

class CustomerDocumentSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    
    class Meta:
        model = CustomerDocument
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'uploaded_at']

class CustomerPaymentSerializer(serializers.ModelSerializer):
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    
    class Meta:
        model = CustomerPayment
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class CustomerListSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source='get_full_name')
    
    class Meta:
        model = Customer
        fields = [
            'id', 'customer_code', 'customer_type', 'company_name',
            'full_name', 'email', 'phone', 'city', 'state',
            'outstanding_amount', 'loyalty_points', 'loyalty_tier',
            'is_active', 'created_at'
        ]

class CustomerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source='get_full_name')
    addresses = CustomerAddressSerializer(many=True, read_only=True)
    contacts = CustomerContactSerializer(many=True, read_only=True)
    interactions = CustomerInteractionSerializer(many=True, read_only=True)
    loyalty = CustomerLoyaltySerializer(read_only=True)
    documents = CustomerDocumentSerializer(many=True, read_only=True)
    recent_payments = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = Customer
        fields = '__all__'
    
    def get_recent_payments(self, obj):
        payments = obj.payments.all()[:5]
        return CustomerPaymentSerializer(payments, many=True).data

class CustomerCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'customer_type', 'company_name', 'first_name', 'last_name',
            'email', 'phone', 'mobile', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'gst_number',
            'pan_number', 'tax_id', 'credit_limit', 'payment_terms',
            'preferred_communication', 'do_not_disturb', 'notes', 'profile_image'
        ]
    
    def validate_email(self, value):
        if Customer.objects.filter(email=value).exists():
            raise serializers.ValidationError("Customer with this email already exists.")
        return value
    
    def validate_gst_number(self, value):
        if value and len(value) != 15:
            raise serializers.ValidationError("GST number must be 15 characters long")
        return value.upper() if value else value

class CustomerInteractionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerInteraction
        fields = [
            'interaction_type', 'subject', 'description', 'contact_person',
            'duration_minutes', 'outcome', 'follow_up_required', 'follow_up_date',
            'priority', 'status'
        ]

class CustomerPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPayment
        fields = [
            'payment_date', 'amount', 'payment_method', 'reference_number',
            'bank_name', 'cheque_number', 'transaction_id', 'invoice_id',
            'invoice_number', 'notes'
        ]
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
