# synchronize two folders: source and replica - full, identical copy
# synchronize the replica
#sync periodically, program stop
#all logged
#we can use build-in library for algorithms

#args: path to source folder, path to replica folder, interval between syncs, amount of sync, path to log file

#Initial logger
import os
import logging
import json
import argparse
import shutil
import hashlib
from time import time
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
    #przejsc do folderu source_folder_path i sprawdzic czy wszystkie pliki sa na miejsu, to znaczy
    # sprawdzic czy sa nowe lub stare pliki, jezeli tak to zaupdatowac, a te co sa to policzyc md5
    def __init__(self, sync_interval, sync_numbers, source_folder_path, replica_folder_path):
        self.sync_interval = sync_interval
        self.sync_numbers = sync_numbers
        self.source_folder_path = source_folder_path
        self.replica_folder_path = replica_folder_path

    def _sync_folders(self):
        pass

    def run(self):
        for i in range(self.sync_numbers):
            self._sync_once()

            if i < self.sync_numbers - 1: # prevent from sleeping at last iteration 
                time.sleep(self.sync_interval)

    def _sync_once(self):
        self._check_and_sync()
        self._remove_extras()
    
    def _check_and_sync(self):
        for root, dirs, files in os.walk(self.source_folder_path):
            source_rel_path = os.path.relpath(root, self.source_folder_path)
            replica_root_path = os.path.join(self.replica_folder_path, source_rel_path)

            if not os.path.exists(replica_root_path):
                os.makedirs(replica_root_path)
            
            for file in files:
                source_file_path = os.path.join(root, file)
                replica_file_path = os.path.join(replica_root_path, file)

                if not os.path.exists(replica_file_path) or self._file_changed(source_file_path, replica_file_path):
                    shutil.copy2(source_file_path, replica_file_path)

    def _remove_extras(self):
        for root, dirs, files in os.walk(self.source_folder_path, topdown=False):
            source_rel_path = os.path.relpath(root, self.source_folder_path)
            replica_root_path = os.path.join(self.replica_folder_path, source_rel_path)
            
            for file in files:
                source_file_path = os.path.join(root, file)
                replica_file_path = os.path.join(replica_root_path, file)
            
                if not os.path.exists(source_file_path):
                    os.remove(replica_file_path)
            
            for dir in dirs:
                replica_dir_path = os.path.join(root, dir)
                source_dir_path = os.path.join(source_rel_path)

                if not os.path.exists(source_dir_path):
                    shutil.rmtree(replica_dir_path)


    def _sha256_check(self, file_path):
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    def _file_changed(self, file_1, file_2):
        return self._sha256_check(file_1) == self._sha256_check(file_2)
        


if __name__ == "__main__":
    parser = CLIParser()
    test = parser.load_config()
    print(test)

    test2 = SynchronizeFiles(
        test.sync_interval,
        test.sync_numbers,
        test.source_folder_path,
        test.replica_folder_path
    )

    test2._check_and_sync()