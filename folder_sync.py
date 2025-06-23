import os
import logging
import json
import argparse
import shutil
import hashlib

from time import time
from dataclasses import dataclass

logger = logging.getLogger("folder_sync")


@dataclass
class Config:
    """Holds configuration settings parsed from command-line args.

    Attributes:
        source_folder_path (str): Path to source folder
        replica_folder_path (str): Path to replica folder
        sync_interval (int): Number of intervals between synchronizations
        sync_numbers (int): Total number of synchronization runs
        log_file_path (str): Path to log file (json format)
    """

    source_folder_path: str
    replica_folder_path: str
    sync_interval: int
    sync_numbers: int
    log_file_path: str


class CLIParser:
    """Reads the required arguments for the folder synchronization program."""

    def __init__(self):
        """Initializes the CLIParser"""
        self.parser = argparse.ArgumentParser(
            description="One-way folder synchronization tool"
        )
        self._setup_arguments()

    def _setup_arguments(self):
        """Defines expected arguments.

        Args:
            source_folder_path (str): Path to source folder
            replica_folder_path (str): Path to replica folder
            sync_interval (int): Number of intervals between synchronizations
            sync_numbers (int): Total number of synchronization runs
            log_file_path (str): Path to log file (json format)
        """
        self.parser.add_argument(
            "source_folder_path", type=str, help="Path to source folder"
        )
        self.parser.add_argument(
            "replica_folder_path", type=str, help="Path to replica folder"
        )
        self.parser.add_argument(
            "sync_interval",
            type=int,
            help="Number of intervals between synchronizations",
        )
        self.parser.add_argument(
            "sync_numbers", type=int, help="Total number of synchronization runs"
        )
        self.parser.add_argument(
            "log_file_path", type=str, help="Path to log file (json format)"
        )

    def load_config(self):
        """Parses the CLI arguments and returns them as Config dataclass.

        Returns:
            Config: Object containing all parsed arguments
        """
        try:
            raw_args = self.parser.parse_args()
            return Config(**vars(raw_args))
        except argparse.ArgumentError as err:
            print(f"Argument parsing error: {err}")
            raise
        except SystemExit as err:
            print(f"Invalid command-line arguments or --help called. Error: {err}")
            raise


class JsonLogFormatter(logging.Formatter):
    """Custom log formatter that formats logs in JSON structure for file log output."""

    def format(self, record):
        """Format log record into JSON string.

        Args:
            record: Log record containing event information

        Returns:
            JSON formatted string
        """
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_record, ensure_ascii=False)


class ConsoleLogFormatter(logging.Formatter):
    """Custom log formatter for console log output."""

    def format(self, record):
        """Format log record for console output.

        Args:
            record: Log record containing event information

        Returns:
            Formatted string with timestamp, log level and message
        """
        return f"[{self.formatTime(record)}] {record.levelname} {record.getMessage()}"


class LoggerConfigurator:
    """Configures logging to the JSON log file and to the console.

    Attributes:
        file_log_path (str): path to the log file
        logger_name (str): name of the logger
    """

    def __init__(self, file_log_path, logger_name="folder_sync"):
        """Initializes the LoggerConfigurator.

        Attributes:
            file_log_path (str): path to the log file
            logger_name (str): name of the logger (defaults to "folder_sync")
        """
        self.file_log_path = file_log_path
        self.logger_name = logger_name

    def setup_logger(self):
        """Configure the logger with file and console handlers.

        Returns:
            logging.Logger: Configured logger object
        """
        console_log_level = "INFO"
        file_log_level = "ERROR"

        logger = logging.getLogger(self.logger_name)
        logger.handlers.clear()

        # File handler
        file_handler = logging.FileHandler(
            self.file_log_path, mode="w", encoding="utf-8"
        )
        file_handler.setFormatter(JsonLogFormatter())
        file_handler.setLevel(getattr(logging, file_log_level))

        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ConsoleLogFormatter())
        console_handler.setLevel(getattr(logging, console_log_level))

        logger.addHandler(console_handler)


class SynchronizeFiles:
    """Performs one-way synchronization between given source and replica folders

    Attributes:
        sync_interval (int): Interval in seconds between sync runs
        sync_numbers (int): Number of total sync cycles
        source_folder_path (str): Absolute path to the source folder
        replica_folder_path (str): Absolute path to the replica folder
    """

    def __init__(
        self, sync_interval, sync_numbers, source_folder_path, replica_folder_path
    ):
        """Initializes the SynchronizeFiles

        Args:
            sync_interval (int): Interval in seconds between sync runs
            sync_numbers (int): Number of total sync cycles
            source_folder_path (str): Absolute path to the source folder
            replica_folder_path (str): Absolute path to the replica folder
        """
        self.sync_interval = sync_interval
        self.sync_numbers = sync_numbers
        self.source_folder_path = source_folder_path
        self.replica_folder_path = replica_folder_path

    def run(self):
        """Executes sync process for specified number of times"""
        for i in range(self.sync_numbers):
            logger.info(f"Starting sync run {i + 1}/{self.sync_numbers}")
            self._sync_once()
            logger.info(f"Finished sync run {i + 1}/{self.sync_numbers}")

            if i < self.sync_numbers - 1:  # prevent from sleeping at last iteration
                logger.debug(f"Sleeping for {self.sync_interval} seconds")
                time.sleep(self.sync_interval)

    def _sync_once(self):
        """Performs single full sync which include adding, updating and removing files"""
        self._check_and_sync()
        self._remove_extras()

    def _check_and_sync(self):
        """Synchronizes the source folder with the replica folder by copying new or modified files from the source folder"""
        for root, _, files in os.walk(self.source_folder_path):
            replica_root_path = self._get_replica_root_path(root)

            if not os.path.exists(replica_root_path):
                os.makedirs(replica_root_path)

            for file in files:
                source_file_path = os.path.join(root, file)
                replica_file_path = os.path.join(replica_root_path, file)

                if not os.path.exists(replica_file_path) or self._file_changed(
                    source_file_path, replica_file_path
                ):
                    shutil.copy2(source_file_path, replica_file_path)

    def _remove_extras(self):
        """Removes files and directories from the replica folder that no longer exist in the source folder"""
        for root, dirs, files in os.walk(self.source_folder_path, topdown=False):
            source_rel_path = os.path.relpath(root, self.source_folder_path)
            replica_root_path = self._get_replica_root_path(root)

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
        """Computes the SHA-256 hash of the given file

        Args:
            file_path (str): Absolute path to the file for hash calculation

        Returns:
            str: The SHA-256 hexadecimal digest of the file
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    def _file_changed(self, file_1, file_2):
        """Compares two files to determine if their contents differ using SHA-256 hashing

        Args:
            file_1 (str): Path to the first file
            file_2 (str): Path to the second file

        Returns:
            bool: False if the files differ"""
        return self._sha256_check(file_1) == self._sha256_check(file_2)

    def _get_replica_root_path(self, root_path):
        source_rel_path = os.path.relpath(root_path, self.source_folder_path)
        return os.path.join(self.replica_folder_path, source_rel_path)


def main():
    # Parse arguments
    parser = CLIParser()
    test = parser.load_config()
    print(test)

    # Configure logger
    LoggerConfigurator(test.log_file_path).setup_logger()

    test2 = SynchronizeFiles(
        test.sync_interval,
        test.sync_numbers,
        test.source_folder_path,
        test.replica_folder_path,
    )

    test2.run()


if __name__ == "__main__":
    main()
