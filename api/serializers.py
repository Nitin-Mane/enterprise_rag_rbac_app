from rest_framework import serializers

from .models import DataSource, EnterpriseUser, QueryAudit


class EnterpriseUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnterpriseUser
        fields = ["id", "username", "display_name", "department", "role", "clearance"]


class DataSourceSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DataSource
        fields = [
            "id",
            "source_id",
            "title",
            "source_type",
            "departments",
            "allowed_roles",
            "min_clearance",
            "sensitivity",
            "description",
            "chunk_count",
        ]


class QueryAuditSerializer(serializers.ModelSerializer):
    user = EnterpriseUserSerializer(read_only=True)

    class Meta:
        model = QueryAudit
        fields = ["id", "user", "question", "routed_sources", "blocked_sources", "confidence", "created_at"]
