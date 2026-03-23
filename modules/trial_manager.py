import datetime
import json

class TrialManager:
    def __init__(self):
        self.trial_expiration = datetime.timedelta(days=7)
        self.trial_start = datetime.datetime.now()
        self.trial_end = self.trial_start + self.trial_expiration
        self.trial_active = True

    def check_trial_status(self):
        if self.trial_active:
            if self.trial_end < datetime.datetime.now():
                self.trial_active = False
                return False
            else:
                return True
        else:
            return False

    def start_trial(self):
        self.trial_start = datetime.datetime.now()
        self.trial_end = self.trial_start + self.trial_expiration
        self.trial_active = True

    def end_trial(self):
        self.trial_active = False

    def get_trial_status(self):
        return {
            'trial_active': self.trial_active,
            'trial_start': self.trial_start,
            'trial_end': self.trial_end
        }
