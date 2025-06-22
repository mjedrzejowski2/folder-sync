# synchronize two folders: source and replica - full, identical copy
# synchronize the replica
#sync periodically, program stop
#all logged
#we can use build-in library for algorithms

#args: path to source folder, path to replica folder, interval between syncs, amount of sync, path to log file

#Initial logger
import logging
import json
import argparse
from dataclasses import dataclass


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno
        }
        return json.dumps(log_record, ensure_ascii=False)
    
class ConsoleLogFormatter(logging.Formatter):
    def format(self, record):
        return f"[{self.formatTime(record)}] {record.levelname} {record.getMessage()}"
        

class LoggerConfigurator():
    def __init__(self, file_log_path, logger_name="folder_sync"):
        self.file_log_path = file_log_path
        self.logger_name = logger_name

    def setup_logger(self):
        console_log_level = "INFO"
        file_log_level = "ERROR"

        logger = logging.getLogger(self.logger_name)
        logger.handlers.clear()

        #File handler
        file_handler = logging.FileHandler(self.file_log_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(JsonLogFormatter())
        file_handler.setLevel(getattr(logging, file_log_level))

        logger.addHandler(file_handler)

        #Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(LoggerConfigurator())
        console_handler.setLevel(getattr(logging, console_log_level))

        logger.addHandler(console_handler)


class CLIParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self._setup_arguments()

    def _setup_arguments(self):
        self.parser.add_argument("source_folder_path", type=str, help="Path to source folder")
        self.parser.add_argument("replica_folder_path", type=str, help="Path to replica folder")
        self.parser.add_argument("sync_interval", type=int, help="Number of intervals between synchronizations")
        self.parser.add_argument("sync_numbers", type=int, help="Amount of synchronizations")
        self.parser.add_argument("log_file_path", type=str, help="Path to log file (json format)")

    def load_config(self):
        raw_args = self.parser.parse_args()
        return Config(**vars(raw_args))        


@dataclass
class Config:
    source_folder_path: str
    replica_folder_path: str
    sync_interval: int
    sync_numbers: int
    log_file_path: str



class SynchronizeFiles:
    def __init__(self, sync_interval, sync_numbers, source_folder_path, replica_folder_path):
        self.sync_interval = sync_interval
        self.sync_numbers = sync_numbers
        self.source_folder_path = source_folder_path
        self.replica_folder_path = replica_folder_path

    def _sync_folders(self):
        pass

    def run(self):
        for i in range(self.sync_numbers):
            pass 
        


if __name__ == "__main__":
    parser = CLIParser()
    test = parser.load_config()
    print(test)