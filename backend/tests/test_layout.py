import ast
import importlib
import json
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve

from database import collections, connection


class LayoutTests(SimpleTestCase):
    def test_all_original_route_declarations_are_preserved(self):
        contract = json.loads(Path(__file__).with_name('route_contract.json').read_text())
        backend = Path(__file__).resolve().parents[1]
        for module, declarations in contract.items():
            with self.subTest(module=module):
                tree = ast.parse((backend / module / 'urls.py').read_text(encoding='utf-8'))
                actual = [ast.unparse(n) for n in ast.walk(tree)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                          and n.func.id == 'path']
                self.assertEqual(actual, declarations)
                if module != 'finedge_backend':
                    self.assertEqual(apps.get_app_config(module).name, module)

    def test_workflow_routes_resolve(self):
        for path, view in [
            ('auth/login/', 'LoginView'),
            ('candidates/CAND-0001/create-employee/', 'CandidateCreateEmployeeView'),
            ('employees/onboarding/', 'EmployeeOnboardingListView'),
            ('employees/sample/onboarding-steps/step/status/', 'EmployeeOnboardingStepStatusView'),
            ('employees/sample/initiate-exit/', 'InitiateExitView'),
            ('separations/SEP-0001/steps/step/status/', 'SeparationStepStatusView'),
            ('candidates/CAND-0001/public-upload/', 'PublicDocUploadView'),
        ]:
            with self.subTest(path=path):
                self.assertEqual(resolve('/api/v1/' + path).func.view_class.__name__, view)

    def test_runtime_paths_and_deployment_imports(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(settings.BASE_DIR, root)
        self.assertTrue((root / 'backend/manage.py').is_file())
        for module in ('finedge_backend.wsgi', 'finedge_backend.asgi'):
            self.assertTrue(callable(importlib.import_module(module).application))

    def test_collection_access_uses_one_lazy_client(self):
        connection.get_database.cache_clear()
        try:
            with patch.object(connection, 'MongoClient') as client:
                collections.get_users_collection()
                collections.get_employees_collection()
                self.assertEqual(client.call_count, 1)
        finally:
            connection.get_database.cache_clear()
