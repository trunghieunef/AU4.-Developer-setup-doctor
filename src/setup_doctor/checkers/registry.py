# src/setup_doctor/checkers/registry.py   (stub, replaced in Task 10)
from .base import Checker

class RegistryChecker(Checker):
    id, label, ecosystem = "registry", "Registry/credentials", "registry"
    def run(self, ctx):
        return []