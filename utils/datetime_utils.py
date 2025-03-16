from datetime import datetime, timedelta
import pandas as pd
from dateutil import parser
from config.app_config import AppConfig

class DatetimeUtils:
    def __init__(self, logger=None):
        self.logger = logger
        self.config = AppConfig()
    
    def determine_input_period(self, input_period: int):
        if input_period < 1 or input_period > 24 :
            return self.config.DEFAULT_PERIOD

        return input_period
    
    def generate_date_range(self, inputDate: str):
        date_obj = pd.to_datetime(inputDate)
        last_day = date_obj - pd.Timedelta(days=1)
        parse_from = parser.isoparse(f'{last_day.strftime("%Y-%m-%d")}T17:00:00.000Z')
        parse_to = parser.isoparse(f'{inputDate}T17:00:00.000Z')
        
        if self.logger:
            self.logger.info(f"Generated date range: start_date {parse_from} | end_date {parse_to}")
        
        return { "start_date": parse_from, "end_date": parse_to }
    
    def generate_period(self, input_period: int, start_date: datetime, end_date: datetime):
        result_period = []

        while start_date < end_date:
            next_end_time = start_date + timedelta(hours=input_period)
            end_time = min(next_end_time, end_date)

            result_period.append({
                'start_date': start_date.isoformat(timespec='milliseconds'),
                'end_date': end_time.isoformat(timespec='milliseconds'),
            })

            start_date = end_time

        if self.logger:
            self.logger.info(f"Input period: {input_period}")
            self.logger.info(f"Generated period: {result_period}")

        return result_period
    
    def convert_datetime(self, dt_str: str):
        return parser.isoparse(dt_str).astimezone()
