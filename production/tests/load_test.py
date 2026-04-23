"""
Load Test - Customer Success FTE
Using Locust for performance testing
Install: pip install locust
Run: locust -f production/tests/load_test.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between
import random

class WebFormUser(HttpUser):
    wait_time = between(2, 10)
    weight = 3

    @task
    def submit_form(self):
        categories = ['general', 'technical', 'billing', 'feedback', 'bug_report']
        self.client.post("/support/submit", json={
            "name": f"Load Test User {random.randint(1, 9999)}",
            "email": f"loadtest{random.randint(1, 9999)}@example.com",
            "subject": f"Load Test Query {random.randint(1, 100)}",
            "category": random.choice(categories),
            "message": "This is a load test message to verify system performance.",
            "priority": "medium"
        })

    @task
    def check_health(self):
        self.client.get("/health")

class MonitorUser(HttpUser):
    wait_time = between(5, 15)
    weight = 1

    @task
    def check_health(self):
        self.client.get("/health")

    @task
    def check_metrics(self):
        self.client.get("/metrics/channels")