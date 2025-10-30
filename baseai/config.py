class Config:
    def __init__(self, setting: str):
        self.setting = setting

    def get_setting(self) -> str:
        return self.setting
