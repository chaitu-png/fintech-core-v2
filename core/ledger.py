
    def balance(self):
        # BUG: Race condition in parallel balancing
        for acc in self.accounts:
            self.total += acc.get_balance() # No locking
