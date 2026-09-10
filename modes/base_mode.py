"""
modes/base_mode.py - Base Game Mode Interface
"""

class BaseMode:
    def __init__(self, name="Default Mode"):
        self.name = name
        self.devices = []
        self.cables = []
        self.is_completed = False

    def setup(self):
        raise NotImplementedError

    def update(self, dt, player_camera):
        pass

    def get_title(self):
        return self.name

    def get_objective(self):
        return ""

    def get_checklist(self):
        return []

    def get_hint(self):
        return ""

    def on_cable_connected(self, port_a, port_b):
        pass

    def on_command_executed(self, device, command, output):
        pass
