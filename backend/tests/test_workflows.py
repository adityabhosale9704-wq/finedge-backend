"""Real MongoDB/API regression checks using only a uniquely named disposable database.

Opt in with HRMS_TEST_MONGO_URI; .env/MONGO_URI is never used by these tests.
"""
import io
import json
import os
import tempfile
import threading
import uuid
from contextlib import redirect_stdout
from datetime import date, timedelta
from unittest import SkipTest
from unittest.mock import patch
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.wsgi import get_wsgi_application
from django.test import SimpleTestCase, override_settings
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from rest_framework.test import APIClient

from database.create_indexes import create_indexes


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
                   CORS_ALLOWED_ORIGINS=['http://127.0.0.1:5500'])
class WorkflowTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        uri = os.getenv('HRMS_TEST_MONGO_URI')
        if not uri:
            raise SkipTest('Set HRMS_TEST_MONGO_URI to an isolated development MongoDB server.')
        cls.mongo = MongoClient(uri, serverSelectionTimeoutMS=3000)
        try:
            cls.mongo.admin.command('ping')
        except PyMongoError:
            cls.mongo.close()
            raise RuntimeError('HRMS_TEST_MONGO_URI is unavailable; connection details withheld.') from None
        cls.db_name = 'hrms_refactor_test_' + uuid.uuid4().hex
        cls.db = cls.mongo[cls.db_name]
        cls.addClassCleanup(cls.mongo.close)
        cls.addClassCleanup(lambda: cls.mongo.drop_database(cls.db_name))
        cls.store_patch = patch('database.collections.get_database', return_value=cls.db)
        cls.store_patch.start()
        cls.addClassCleanup(cls.store_patch.stop)
        with redirect_stdout(io.StringIO()):
            create_indexes(cls.db)

    def setUp(self):
        for name in self.db.list_collection_names():
            self.db[name].delete_many({})
        self.media = tempfile.TemporaryDirectory(prefix='hrms-test-media-')
        self.addCleanup(self.media.cleanup)
        storage = override_settings(MEDIA_ROOT=self.media.name)
        storage.enable()
        self.addCleanup(storage.disable)
        self.db.users.insert_one({
            'email': 'synthetic@example.invalid', 'name': 'Synthetic HR',
            'role': 'employee', 'password': make_password('test-only-password'),
        })
        self.api = APIClient()
        response = self.api.post('/api/v1/auth/login/', {
            'email': 'synthetic@example.invalid', 'password': 'test-only-password',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['token'])

    def post(self, path, data=None, expected=200):
        response = self.api.post('/api/v1/' + path, data or {}, format='json')
        self.assertEqual(response.status_code, expected)
        return response.data

    def candidate(self):
        req = self.post('requisitions/', {
            'role': 'Synthetic role', 'branch': 'Synthetic branch',
            'openings': 1, 'raised_by': 'Synthetic HR',
        }, expected=201)
        return self.post('candidates/', {
            'name': 'Synthetic Candidate', 'email': 'candidate@example.invalid',
            'phone': '0000000000', 'requisition_id': req['id'],
        }, expected=201)

    def test_recruitment_documents_onboarding_activation_and_exit(self):
        self.assertEqual(self.api.get('/api/v1/auth/me/').status_code, 200)
        candidate = self.candidate()
        candidate_id = candidate['id']
        for step in candidate['steps']:
            result = self.post(f'candidates/{candidate_id}/steps/{step["id"]}/status/',
                               {'status': 'Completed'})
        self.assertEqual(result['stage'], 'Documents Pending')
        self.post(f'candidates/{candidate_id}/outcome/', {'outcome': 'Selected'})
        self.post(f'candidates/{candidate_id}/create-employee/', expected=400)
        token = self.post(f'candidates/{candidate_id}/send-doc-link/')['upload_token']
        public = f'/api/v1/candidates/{candidate_id}/public-checklist/?token={token}'
        checklist = self.api.get(public)
        self.assertEqual(checklist.status_code, 200)
        self.assertEqual(self.api.get(public + '-invalid').status_code, 404)
        for index, item in enumerate(checklist.data['doc_checklist']):
            file = SimpleUploadedFile('synthetic.txt', b'Synthetic document only', 'text/plain')
            if index == 0:
                path = f'/api/v1/candidates/{candidate_id}/public-upload/?token={token}'
                response = self.api.post(path, {'file': file, 'item_id': item['id']}, format='multipart')
            else:
                path = f'/api/v1/candidates/{candidate_id}/doc-checklist/{item["id"]}/upload/'
                response = self.api.post(path, {'file': file}, format='multipart')
            self.assertEqual(response.status_code, 201)
        converted = self.post(f'candidates/{candidate_id}/create-employee/', expected=201)
        self.assertEqual(set(converted), {'employee_id', 'position_id', 'message'})
        self.post(f'candidates/{candidate_id}/create-employee/', expected=400)
        self.assertEqual(self.db.employees.count_documents({}), 1)
        employee_id = converted['employee_id']
        employees = self.api.get('/api/v1/employees/').data
        self.assertEqual(employees, [])
        onboarding = self.api.get('/api/v1/employees/onboarding/').data
        self.assertEqual(len(onboarding), 1)
        for step in onboarding[0]['onboarding_steps']:
            updated = self.post(f'employees/{employee_id}/onboarding-steps/{step["id"]}/status/',
                                {'status': 'Completed'})
        self.assertEqual(updated['status'], 'Onboarding')
        response = self.api.patch(f'/api/v1/employees/{employee_id}/',
                                  {'policy_accepted': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'Active')
        self.assertTrue(response.data['transition']['moved'])
        self.assertEqual(self.db.candidates.find_one({'id': candidate_id})['lifecycle_status'], 'Employee')
        self.assertEqual(len(self.api.get('/api/v1/employees/').data), 1)
        self.post(f'employees/{employee_id}/onboarding-steps/{onboarding[0]["onboarding_steps"][0]["id"]}/status/',
                  {'status': 'Pending'}, expected=400)
        today = date.today()
        exit_data = {'resignation_date': today.isoformat(),
                     'last_working_day': (today + timedelta(days=30)).isoformat(),
                     'reason': 'Synthetic test'}
        separation = self.post(f'employees/{employee_id}/initiate-exit/', exit_data, expected=201)
        self.post(f'employees/{employee_id}/initiate-exit/', exit_data, expected=400)
        for step in separation['steps']:
            result = self.post(f'separations/{separation["id"]}/steps/{step["id"]}/status/',
                               {'status': 'Completed'})
        self.assertEqual(result['status'], 'Completed')
        employee = self.api.get(f'/api/v1/employees/{employee_id}/').data
        self.assertEqual(employee['status'], 'Leaver')
        self.assertIsNone(employee['position_id'])
        position = self.db.positions.find_one({'id': converted['position_id']})
        self.assertEqual(position['status'], 'Vacant')
        self.assertIsNone(position['current_employee_id'])
        self.assertIsNotNone(position['history'][0]['end_date'])
        history = self.api.get(f'/api/v1/audit/employee/{employee_id}/').data
        self.assertTrue(any(entry['to'] == 'Leaver' for entry in history))

    def test_validation_authentication_and_frozen_candidate_contracts(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.get('/api/v1/employees/').status_code, 401)
        self.assertEqual(anonymous.post('/api/v1/auth/login/', {}, format='json').status_code, 401)
        response = self.api.get('/api/v1/employees/invalid-id/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {'detail': 'Employee not found.'})
        candidate = self.candidate()
        self.db.candidates.update_one({'id': candidate['id']}, {'$set': {'frozen': True}})
        response = self.post(f'candidates/{candidate["id"]}/steps/{candidate["steps"][0]["id"]}/status/',
                             {'status': 'Completed'}, expected=400)
        self.assertIn('frozen', response['detail'])
        self.post(f'candidates/{candidate["id"]}/steps/missing/status/', {'status': 'Invalid'}, expected=400)

    def test_sop_snapshots_and_index_constraints(self):
        candidate = self.candidate()
        original = candidate['steps'][0]['how']
        sop = self.api.get('/api/v1/sop/recruitment/steps/').data
        response = self.api.patch('/api/v1/sop/steps/' + sop[0]['id'] + '/',
                                  {'how': 'Changed synthetic SOP'}, format='json')
        self.assertEqual(response.status_code, 200)
        stored = self.db.candidates.find_one({'id': candidate['id']})
        self.assertEqual(stored['steps'][0]['how'], original)
        self.assertEqual(self.candidate()['steps'][0]['how'], 'Changed synthetic SOP')
        indexes = self.db.employees.index_information()
        self.assertTrue(any(i.get('unique') and i['key'] == [('source_candidate_id', 1)]
                            for i in indexes.values()))
        with redirect_stdout(io.StringIO()):
            create_indexes(self.db)

    def test_feature_lists_and_shared_aggregations(self):
        for path in ('employees/', 'positions/', 'requisitions/', 'candidates/', 'tasks/',
                     'departments/', 'branches/', 'roles/', 'workindia/',
                     'salary-structure/', 'salary-revisions/', 'incentive-structures/',
                     'separations/', 'engagement/contests/', 'engagement/suggestions/',
                     'engagement/activities/', 'compliance/', 'done-board/',
                     'interview-questions/', 'reference-checks/', 'policies/',
                     'policies-acceptance-stats/', 'letter-templates/', 'notifications/',
                     'workflow-templates/Recruitment/steps/'):
            with self.subTest(path=path):
                self.assertEqual(self.api.get('/api/v1/' + path).status_code, 200)

    def test_shared_id_generator_preserves_existing_ids(self):
        from database.queries import generate_next_sequential_id

        self.db.tasks.insert_many([{'id': 'TASK-0002'}, {'id': 'TASK-invalid'},
                                   {'id': 'OTHER-1000'}, {'id': 'TASK-0010'}])
        self.assertEqual(generate_next_sequential_id(self.db.tasks, 'TASK'), 'TASK-0011')

    def test_http_frontend_origin_can_reach_login(self):
        class QuietHandler(WSGIRequestHandler):
            def log_message(self, *args):
                pass

        with make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=QuietHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = b'{"email":"synthetic@example.invalid","password":"test-only-password"}'
                request = Request(f'http://127.0.0.1:{server.server_port}/api/v1/auth/login/',
                                  data=payload, headers={'Content-Type': 'application/json',
                                                        'Origin': 'http://127.0.0.1:5500'})
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers['Access-Control-Allow-Origin'],
                                     'http://127.0.0.1:5500')
                    self.assertIn('token', json.loads(response.read()))
            finally:
                server.shutdown()
                thread.join(timeout=5)
