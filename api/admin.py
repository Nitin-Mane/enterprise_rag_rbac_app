from django.contrib import admin

from .models import DataSource, DocumentChunk, EnterpriseUser, QueryAudit


admin.site.register(EnterpriseUser)
admin.site.register(DataSource)
admin.site.register(DocumentChunk)
admin.site.register(QueryAudit)
