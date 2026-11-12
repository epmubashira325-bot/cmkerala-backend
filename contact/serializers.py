from rest_framework import serializers
from .models import ContactEnquiry


class ContactEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEnquiry
        fields = ('id', 'name', 'email', 'subject', 'message', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate_name(self, value):
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters long.")
        return val

    def validate_subject(self, value):
        val = value.strip()
        if len(val) < 3:
            raise serializers.ValidationError("Subject must be at least 3 characters long.")
        return val

    def validate_message(self, value):
        val = value.strip()
        if len(val) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long.")
        return val

