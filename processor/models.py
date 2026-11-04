import uuid
from django.db import models


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40, db_index=True)
    name = models.CharField(max_length=255)
    columns = models.JSONField()
    original_rows = models.JSONField()
    rows = models.JSONField()
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class Operation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    description = models.TextField()
    pattern = models.TextField()
    columns = models.JSONField()
    replacement = models.TextField()
    ignore_case = models.BooleanField(default=False)
    row_filters = models.JSONField(default=list)
    source_version = models.PositiveIntegerField()
    applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
