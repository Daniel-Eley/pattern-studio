import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import Dataset
from .services import InputError, PatternPlan, export_data, generate_plan, parse_upload, transform


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, DEMO_MODE=True)
class WorkflowTests(TestCase):
    def setUp(self):
        self.client.get('/api/bootstrap/')
        file = SimpleUploadedFile('people.csv', b'ID,Name,Email\n001,John Doe,john.doe@example.com\n002,Jane Smith,jane_smith@domain.com\n003,Alice Brown,alice.brown@website.org\n')
        result = self.client.post('/api/datasets/', {'file': file})
        self.assertEqual(result.status_code, 201)
        self.data = result.json()
        self.url = f'/api/datasets/{self.data["id"]}/'

    def preview(self, **kwargs):
        return self.client.post(self.url + 'preview/', {'description': 'Find email addresses in the Email column', 'replacement': 'REDACTED', **kwargs}, content_type='application/json')

    def test_complete_workflow_and_original_reset(self):
        preview = self.preview().json()
        self.assertEqual(preview['matches'], 3)
        self.assertEqual(preview['columns'], ['Email'])
        self.assertEqual(self.client.get(self.url).json()['version'], 0)
        result = self.client.post(self.url + f'apply/{preview["operation_id"]}/').json()
        self.assertEqual(result['rows'][0], ['001', 'John Doe', 'REDACTED'])
        self.assertIn(b'REDACTED', self.client.get(self.url + 'download/').content)
        exported = self.client.get(self.url + 'download/?format=xlsx')
        book = openpyxl.load_workbook(io.BytesIO(exported.content))
        self.assertEqual(book.active['C2'].value, 'REDACTED')
        reset = self.client.post(self.url + 'reset/').json()
        self.assertEqual(reset['rows'][0][2], 'john.doe@example.com')

    def test_session_isolation(self):
        stranger = Client()
        self.assertEqual(stranger.get(self.url).status_code, 404)
        self.assertEqual(stranger.get(self.url + 'download/').status_code, 404)
        self.assertEqual(stranger.post(self.url + 'reset/').status_code, 404)

    def test_stale_preview_and_duplicate_apply(self):
        first = self.preview().json()
        second = self.preview().json()
        self.assertEqual(self.client.post(self.url + f'apply/{first["operation_id"]}/').status_code, 200)
        self.assertEqual(self.client.post(self.url + f'apply/{first["operation_id"]}/').status_code, 409)
        self.assertEqual(self.client.post(self.url + f'apply/{second["operation_id"]}/').status_code, 409)

    def test_empty_replacement_and_literal_backslash(self):
        preview = self.preview(replacement=r'\1 $1').json()
        result = self.client.post(self.url + f'apply/{preview["operation_id"]}/').json()
        self.assertEqual(result['rows'][0][2], r'\1 $1')
        self.client.post(self.url + 'reset/')
        preview = self.preview(replacement='').json()
        result = self.client.post(self.url + f'apply/{preview["operation_id"]}/').json()
        self.assertEqual(result['rows'][0][2], '')

    def test_validation_and_delete(self):
        for overrides in ({'columns': ['Missing']}, {'description': ''}, {'replacement': 42}, {'columns': 'Email'}):
            self.assertEqual(self.preview(**overrides).status_code, 400)
        self.assertEqual(self.client.post(self.url + 'preview/', '[]', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.get(self.url + '?page=-1').status_code, 400)
        self.assertEqual(self.client.post(self.url + 'delete/').status_code, 200)
        self.assertFalse(Dataset.objects.exists())

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/bootstrap/')
        self.assertEqual(client.post('/api/datasets/').status_code, 403)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/datasets/', HTTP_X_CSRFTOKEN=token).status_code, 400)


class ServicesTests(TestCase):
    def test_bad_files(self):
        for name, raw in [('x.csv', b''), ('x.csv', b'a,a\n1,2'), ('x.csv', b'a,b\n1'), ('x.exe', b'bad'), ('x.xlsx', b'bad')]:
            with self.assertRaises(InputError):
                parse_upload(SimpleUploadedFile(name, raw))

    def test_excel_preserves_numbers_and_blanks(self):
        book = openpyxl.Workbook()
        book.active.append(['ID', 'Text', 'Blank'])
        book.active.append([12, 'email@example.com', None])
        output = io.BytesIO(); book.save(output)
        columns, rows = parse_upload(SimpleUploadedFile('book.xlsx', output.getvalue()))
        self.assertEqual(rows, [[12, 'email@example.com', None]])
        result, _ = transform(rows, columns, r'\d+', ['ID', 'Text'], 'x')
        self.assertEqual(result[0][0], 12)

    def test_regex_errors_and_timeout(self):
        for pattern in ('[', 'a*'):
            with self.assertRaises(InputError):
                transform([['abc']], ['a'], pattern, ['a'], 'x')
        with self.assertRaisesRegex(InputError, 'too long'):
            transform([['a' * 10000 + '!']], ['a'], '(a+)+$', ['a'], 'x')

    def test_formula_export_protection(self):
        content, _ = export_data(['=header'], [['=1+1'], [' +SUM(A1)'], ['@SUM(A1)']], 'csv')
        self.assertIn(b"'=1+1", content)
        self.assertIn(b"' +SUM", content)
        self.assertIn(b"'=header", content)

    @override_settings(DEMO_MODE=False, LLM_PROVIDER='openai')
    @patch('processor.services.OpenAI')
    def test_real_llm_adapter_passes_no_cell_data(self, mock_client):
        plan = PatternPlan(pattern=r'\d{3}', columns=['Code'], ignore_case=False, explanation='Three digits')
        mock_client.return_value.responses.parse.return_value = SimpleNamespace(output_parsed=plan)
        self.assertEqual(generate_plan('Find three digits', ['Code']), plan)
        call = mock_client.return_value.responses.parse.call_args.kwargs
        self.assertFalse(call['store'])
        payload = json.loads(call['input'][1]['content'])
        self.assertEqual(set(payload), {'description', 'available_columns'})

    @override_settings(DEMO_MODE=False, LLM_PROVIDER='openai')
    @patch('processor.services.OpenAI')
    def test_model_refusal(self, mock_client):
        mock_client.return_value.responses.parse.return_value = SimpleNamespace(output_parsed=None)
        with self.assertRaises(InputError):
            generate_plan('Find a pattern', ['Code'])

    @override_settings(DEMO_MODE=False, LLM_PROVIDER='groq')
    @patch.dict('os.environ', {'GROQ_API_KEY': 'test-only-key'})
    @patch('processor.services.OpenAI')
    def test_groq_adapter_and_validation(self, mock_client):
        plan = PatternPlan(pattern=r'\d{3}', columns=['Code'], ignore_case=False, explanation='Three digits')
        completion = mock_client.return_value.chat.completions.create
        completion.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=plan.model_dump_json()))])
        self.assertEqual(generate_plan('Find three digits', ['Code']), plan)
        self.assertEqual(mock_client.call_args.kwargs['base_url'], 'https://api.groq.com/openai/v1')
        args = completion.call_args.kwargs
        self.assertTrue(args['response_format']['json_schema']['strict'])
        self.assertFalse(args['response_format']['json_schema']['schema']['additionalProperties'])
        self.assertEqual(set(json.loads(args['messages'][1]['content'])), {'description', 'available_columns'})
        completion.return_value.choices[0].message.content = '{"pattern": 3}'
        with self.assertRaisesRegex(InputError, 'invalid pattern plan'):
            generate_plan('Find digits', ['Code'])
        completion.return_value.choices[0].finish_reason = 'length'
        with self.assertRaisesRegex(InputError, 'could not complete'):
            generate_plan('Find digits', ['Code'])

    @override_settings(DEMO_MODE=False, LLM_PROVIDER='groq')
    @patch.dict('os.environ', {'GROQ_API_KEY': ''})
    def test_missing_groq_key(self):
        with self.assertRaisesRegex(InputError, 'GROQ_API_KEY'):
            generate_plan('Find digits', ['Code'])
