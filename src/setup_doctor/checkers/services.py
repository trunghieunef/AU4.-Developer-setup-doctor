# src/setup_doctor/checkers/services.py   (stub, replaced in Task 9)
from .base import Checker

class ServicesChecker(Checker):
    id, label, ecosystem = "services", "Local services", "services"
    def run(self, ctx):
        return []