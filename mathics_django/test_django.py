# pages/tests.py
import json
from django.test import SimpleTestCase, TestCase


class HomePageTests(SimpleTestCase):
    def test_home_page_status_code(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_home_page_does_not_contain_incorrect_html(self):
        response = self.client.get("/")
        self.assertNotContains(response, "Hi there! I should not be on the page.")


class CompletionsEndpointTests(TestCase):
    def test_completions_endpoint_returns_system_symbols(self):
        response = self.client.get("/ajax/completions/")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("symbols", payload)
        names = {item["name"] for item in payload["symbols"]}
        self.assertIn("Sin", names)
        self.assertIn("Integrate", names)

    def test_completions_prefix_filter(self):
        response = self.client.get("/ajax/completions/", {"prefix": "Integ"})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        names = [item["name"] for item in payload["symbols"]]
        self.assertIn("Integrate", names)
        self.assertTrue(all("integ" in name.lower() for name in names))

