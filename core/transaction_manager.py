
import threading
import time

class TransactionManager:
    def __init__(self, accounts):
        self.accounts = accounts

    def transfer(self, from_id, to_id, amount):
        # BUG: Race condition - no locking on balance check and update
        if self.accounts[from_id] >= amount:
            time.sleep(0.01) # Simulate delay
            self.accounts[from_id] -= amount
            self.accounts[to_id] += amount
            return True
        return False
