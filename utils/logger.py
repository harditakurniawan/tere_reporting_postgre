from datetime import datetime

class Logger:
    @staticmethod
    def log(level, message):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print(f"{now} - {level.upper()} - {message}\n")

    @staticmethod
    def debug(message):
        Logger.log('DEBUG', message)

    @staticmethod
    def info(message):
        Logger.log('INFO', message)

    @staticmethod
    def warning(message):
        Logger.log('WARNING', message)

    @staticmethod
    def error(message):
        Logger.log('ERROR', message)

    @staticmethod
    def critical(message):
        Logger.log('CRITICAL', message)
