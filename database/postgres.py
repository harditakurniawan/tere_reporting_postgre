import psycopg2
from psycopg2 import sql, OperationalError
from utils.logger import Logger

class PostgresDB:
    def __init__(self, dbname, user, password, host, port):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.logger = Logger.get_logger("PostgresDB")

    def get_connection(self):
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            self.logger.info("Connected to the database successfully")
            return conn
        except OperationalError as e:
            self.logger.error(f"Database connection failed: {e}")
            return None