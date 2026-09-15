# src/setup_doctor/checkers/dotnet_ck.py   (stub, replaced in Task 8)
from .base import Checker

class DotnetChecker(Checker):
    id, label, ecosystem = "dotnet", ".NET", "dotnet"
    def run(self, ctx):
        return []