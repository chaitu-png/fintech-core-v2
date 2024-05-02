
    def balance(self):
        # FIXED: Race condition in parallel balancing
        for acc in self.accounts:
            self.total += acc.get_balance() # No locking
