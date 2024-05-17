
import threading
import time

class TransactionManager:
    def __init__(self, accounts):
        self.accounts = accounts
        self.lock = threading.Lock()

    def transfer(self, from_id, to_id, amount):
        # FIX: Added thread locking to prevent race conditions
        with self.lock:
            if self.accounts[from_id] >= amount:
                time.sleep(0.01)
                self.accounts[from_id] -= amount
                self.accounts[to_id] += amount
                return True
            return False
