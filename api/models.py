from django.db import models


class EnterpriseUser(models.Model):
    username = models.CharField(max_length=80, unique=True)
    display_name = models.CharField(max_length=120)
    department = models.CharField(max_length=80)
    role = models.CharField(max_length=80)
    clearance = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.display_name} ({self.role})"


class DataSource(models.Model):
    SOURCE_TYPES = [
        ("pdf", "PDF"),
        ("csv", "CSV"),
        ("json", "JSON"),
        ("sql", "SQL"),
        ("txt", "Text"),
        ("image", "Image"),
    ]

    source_id = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=180)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    path = models.CharField(max_length=300)
    departments = models.JSONField(default=list)
    allowed_roles = models.JSONField(default=list)
    min_clearance = models.IntegerField(default=1)
    sensitivity = models.CharField(max_length=40, default="internal")
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.IntegerField()
    title = models.CharField(max_length=180)
    content = models.TextField()
    page = models.CharField(max_length=40, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        unique_together = ("source", "chunk_index")

    def __str__(self):
        return f"{self.source.source_id}#{self.chunk_index}"


class QueryAudit(models.Model):
    user = models.ForeignKey(EnterpriseUser, on_delete=models.SET_NULL, null=True)
    question = models.TextField()
    routed_sources = models.JSONField(default=list)
    blocked_sources = models.JSONField(default=list)
    confidence = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
