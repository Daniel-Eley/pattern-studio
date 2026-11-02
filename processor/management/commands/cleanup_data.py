from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from processor.models import Dataset


class Command(BaseCommand):
    help = 'Delete uploaded datasets older than 24 hours; schedule hourly in production.'

    def handle(self, *args, **options):
        count, _ = Dataset.objects.filter(created_at__lt=timezone.now() - timedelta(hours=24)).delete()
        self.stdout.write(f'Deleted {count} expired records.')
