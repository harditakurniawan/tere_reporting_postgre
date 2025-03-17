import configparser
import os

class AppConfig:
    def __init__(self, env_file='.env'):
        self.env_file = env_file
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        self.config.read(self.env_file)
        
        self.BATCH_SIZE = int(self.config.get('APP', 'BATCH_SIZE', fallback=10000))
        self.DEFAULT_PERIOD = int(self.config.get('APP', 'DEFAULT_PERIOD', fallback=3))
        self.TARGET_DIR = self.config.get('APP', 'TARGET_DIR', fallback='./report')
        self.DB_HOST = self.config.get('DB', 'DB_HOST', fallback='127.0.0.1')
        self.DB_PORT = self.config.get('DB', 'DB_PORT', fallback='5432')
        self.DB_NAME = self.config.get('DB', 'DB_NAME', fallback='slreport_db')
        self.DB_USERNAME = self.config.get('DB', 'DB_USERNAME', fallback='')
        self.DB_PASSWORD = self.config.get('DB', 'DB_PASSWORD', fallback='')
