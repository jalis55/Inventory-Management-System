from django.test import SimpleTestCase
from django.urls import reverse


class ApiDocumentationTests(SimpleTestCase):
    def test_openapi_schema_endpoint_is_available(self):
        response = self.client.get(reverse('schema'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/vnd.oai.openapi', response['Content-Type'])

    def test_swagger_ui_endpoint_is_available(self):
        response = self.client.get(reverse('swagger-ui'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'swagger-ui')
        self.assertContains(response, reverse('schema'))

    def test_docs_shortcut_redirects_to_swagger_ui(self):
        response = self.client.get(reverse('api-docs'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('swagger-ui'))

    def test_redoc_endpoint_is_available(self):
        response = self.client.get(reverse('redoc'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'redoc')
