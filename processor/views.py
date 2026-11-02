import json
from datetime import timedelta
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Dataset, Operation
from .services import InputError, export_data, generate_plan, parse_upload, transform


def api_errors(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except (InputError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return JsonResponse({'error': str(exc)}, status=400)
    return wrapped


def body(request):
    try:
        value = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise InputError('Send a valid JSON object.')
    if not isinstance(value, dict):
        raise InputError('Send a JSON object.')
    return value


def text_field(data, key, maximum, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise InputError(f'{key}: provide text up to {maximum} characters.')
    return value


def owned_dataset(request, pk, lock=False):
    query = Dataset.objects.select_for_update() if lock else Dataset.objects
    return get_object_or_404(query, pk=pk, session_key=request.session.session_key or '', created_at__gte=timezone.now() - timedelta(hours=24))


def summary(dataset, page=1):
    start = (page - 1) * 100
    return {'id': str(dataset.id), 'name': dataset.name, 'columns': dataset.columns, 'rows': dataset.rows[start:start + 100], 'row_count': len(dataset.rows), 'version': dataset.version, 'page': page}


@ensure_csrf_cookie
@require_GET
def bootstrap(request):
    if not request.session.session_key:
        request.session.create()
    return JsonResponse({'demo_mode': settings.DEMO_MODE})


@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})


@require_POST
@api_errors
def upload(request):
    if not request.session.session_key:
        request.session.create()
    if Dataset.objects.filter(session_key=request.session.session_key).count() >= 10:
        raise InputError('Session limit reached. Delete a dataset before uploading another.')
    file = request.FILES.get('file')
    if not file:
        raise InputError('Choose a file to upload.')
    columns, rows = parse_upload(file)
    dataset = Dataset.objects.create(session_key=request.session.session_key, name=Path(file.name).name[:255], columns=columns, original_rows=rows, rows=rows)
    return JsonResponse(summary(dataset), status=201)


@require_GET
@api_errors
def detail(request, pk):
    dataset = owned_dataset(request, pk)
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        raise InputError('Page must be a positive integer.')
    if page < 1 or page > max(1, (len(dataset.rows) + 99) // 100):
        raise InputError('Page is out of range.')
    return JsonResponse(summary(dataset, page))


@require_POST
@api_errors
def preview(request, pk):
    dataset = owned_dataset(request, pk)
    data = body(request)
    description = text_field(data, 'description', 1000)
    replacement = text_field(data, 'replacement', 1000, required=False)
    if Operation.objects.filter(dataset__session_key=request.session.session_key, created_at__gte=timezone.now() - timedelta(hours=1)).count() >= 30:
        raise InputError('Preview limit reached (30 per hour per session).')
    selected = data.get('columns')
    if selected is not None and (not isinstance(selected, list) or not selected or any(not isinstance(c, str) or c not in dataset.columns for c in selected)):
        raise InputError('Select valid columns.')
    plan = generate_plan(description, dataset.columns)
    targets = selected if selected is not None else plan.columns
    _, stats = transform(dataset.rows, dataset.columns, plan.pattern, targets, replacement, plan.ignore_case)
    operation = Operation.objects.create(dataset=dataset, description=description, pattern=plan.pattern, columns=targets, replacement=replacement, ignore_case=plan.ignore_case, source_version=dataset.version)
    return JsonResponse({'operation_id': str(operation.id), 'pattern': plan.pattern, 'columns': targets, 'ignore_case': plan.ignore_case, 'explanation': plan.explanation, **stats})


@require_POST
@api_errors
@transaction.atomic
def apply(request, pk, operation_id):
    dataset = owned_dataset(request, pk, lock=True)
    operation = get_object_or_404(Operation, pk=operation_id, dataset=dataset)
    if operation.applied or operation.source_version != dataset.version:
        return JsonResponse({'error': 'The data has changed. Generate a fresh preview.'}, status=409)
    rows, stats = transform(dataset.rows, dataset.columns, operation.pattern, operation.columns, operation.replacement, operation.ignore_case)
    # Optimistic guard also protects SQLite deployments where row locks are unavailable.
    updated = Dataset.objects.filter(pk=dataset.pk, version=operation.source_version).update(rows=rows, version=dataset.version + 1)
    if not updated:
        return JsonResponse({'error': 'The data has changed. Generate a fresh preview.'}, status=409)
    operation.applied = True
    operation.save(update_fields=['applied'])
    dataset.refresh_from_db()
    return JsonResponse({**summary(dataset), **stats})


@require_POST
@transaction.atomic
def reset(request, pk):
    dataset = owned_dataset(request, pk, lock=True)
    dataset.rows = dataset.original_rows
    dataset.version += 1
    dataset.save(update_fields=['rows', 'version'])
    return JsonResponse(summary(dataset))


@require_POST
def delete(request, pk):
    owned_dataset(request, pk).delete()
    return JsonResponse({'deleted': True})


@require_GET
@api_errors
def download(request, pk):
    dataset = owned_dataset(request, pk)
    kind = request.GET.get('format', 'csv')
    if kind not in ('csv', 'xlsx'):
        raise InputError('Export format must be csv or xlsx.')
    content, content_type = export_data(dataset.columns, dataset.rows, kind)
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="processed.{kind}"'
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
def index(request):
    path = settings.BASE_DIR / 'frontend/dist/index.html'
    if not path.exists():
        return HttpResponse('Build the React frontend with npm run build in frontend/.', status=503)
    return FileResponse(path.open('rb'), content_type='text/html')
