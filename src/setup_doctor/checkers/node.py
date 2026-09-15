# src/setup_doctor/checkers/node.py   (stub, replaced in Task 5)
from .base import Checker

class NodeChecker(Checker):
    id, label, ecosystem = "node", "Node.js", "node"
    def run(self, ctx):
        return []