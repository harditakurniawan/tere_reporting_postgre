# app_config.py
import os
from dotenv import load_dotenv

class AppConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        load_dotenv()  
        self.BATCH_SIZE = int(os.getenv('BATCH_SIZE', 10000))
        self.DEFAULT_PERIOD = int(os.getenv('DEFAULT_PERIOD', 3))
        self.TARGET_DIR = os.getenv('TARGET_DIR', './report')
        self.DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
        self.DB_PORT = os.getenv('DB_PORT', '5432')
        self.DB_NAME = os.getenv('DB_NAME', 'slreport_db')
        self.DB_USERNAME = os.getenv('DB_USERNAME', '')
        self.DB_PASSWPRD = os.getenv('DB_PASSWPRD', '')

    def reload_config(self):
        self.load_config()