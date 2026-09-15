# src/setup_doctor/checkers/python_ck.py   (stub, replaced in Task 6)
from .base import Checker

class PythonChecker(Checker):
    id, label, ecosystem = "python", "Python", "python"
    def run(self, ctx):
        return []