import os
import logging
import json
import argparse
import shutil
import hashlib
import time

from pathlib import Path
from dataclasses import dataclass


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
            print(f"Invalid command-line arguments or '--help' called. Error: {err}")
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
        try:
            message = record.getMessage()
        except Exception as err:
            message = f"Failed to format log message. Error:{err}"

        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": message,
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
        try:
            message = record.getMessage()
        except Exception as err:
            message = f"Failed to format log message. Error:{err}"

        return f"[{self.formatTime(record)}] {record.levelname} {message}"


class LoggerConfigurator:
    """Configures logging to the JSON log file and to the console.

    Attributes:
        file_log_path (str): path to the log file
        logger_name (str): name of the logger (defaults to "folder_sync")
    """

    def __init__(self, file_log_path, logger_name="folder_sync"):
        """Initializes the LoggerConfigurator.

        Args:
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
        file_log_level = "INFO"

        logger = logging.getLogger(self.logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        # File handler
        try:
            file_handler = logging.FileHandler(
                self.file_log_path, mode="w", encoding="utf-8"
            )
            file_handler.setFormatter(JsonLogFormatter())
            file_handler.setLevel(getattr(logging, file_log_level))

            logger.addHandler(file_handler)
        except OSError as err:
            print(f"Couldn't initialize log setup for file handler. Error: {err}")

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ConsoleLogFormatter())
        console_handler.setLevel(getattr(logging, console_log_level))

        logger.addHandler(console_handler)
        return logger


class SynchronizeFiles:
    """Performs one-way synchronization between given source and replica folders.

    Attributes:
        sync_interval (int): Interval in seconds between sync runs
        sync_numbers (int): Number of total sync cycles
        source_folder_path (str): Absolute path to the source folder
        replica_folder_path (str): Absolute path to the replica folder
    """

    def __init__(
        self,
        sync_interval,
        sync_numbers,
        source_folder_path,
        replica_folder_path,
        logger,
    ):
        """Initializes the SynchronizeFiles

        Args:
            sync_interval (int): Interval in seconds between sync runs
            sync_numbers (int): Number of total sync cycles
            source_folder_path (str): Absolute path to the source folder
            replica_folder_path (str): Absolute path to the replica folder
            logger (logging.Logger):
        """
        self.sync_interval = sync_interval
        self.sync_numbers = sync_numbers
        self.source_folder_path = Path(source_folder_path).resolve()
        self.replica_folder_path = Path(replica_folder_path).resolve()
        self.logger = logger

    def run(self):
        """Executes sync process for specified number of times."""
        for i in range(self.sync_numbers):
            self.logger.info(f"Starting sync run {i + 1}/{self.sync_numbers}")
            self._sync_once()
            self.logger.info(f"Finished sync run {i + 1}/{self.sync_numbers}")

            if i < self.sync_numbers - 1:  # prevent from sleeping at last iteration
                self.logger.debug(f"Sleeping for {self.sync_interval} seconds")
                time.sleep(self.sync_interval)

    def _sync_once(self):
        """Performs single full sync which include adding, updating and removing files."""
        self._check_and_sync()
        self._remove_extras()

    def _check_and_sync(self):
        """Synchronizes the source folder with the replica folder by copying new or modified files from the source folder."""
        for root, _, files in os.walk(self.source_folder_path):
            root_path = Path(root)
            replica_root_path = self._get_replica_root_path(root_path)

            if replica_root_path is None:
                self.logger.error(f"Skipping sync: Invalid source path {root_path}")
                continue

            if not replica_root_path.exists():
                try:
                    replica_root_path.mkdir(parents=True)
                    self.logger.info(f"Created directory: {replica_root_path}")
                except OSError as err:
                    self.logger.error(
                        f"Failed to create directory {replica_root_path}. Error: {err}"
                    )
                    continue  # no dir no files

            for file in files:
                source_file_path = root_path / file
                replica_file_path = replica_root_path / file

                if not replica_file_path.exists() or self._file_changed(
                    source_file_path, replica_file_path
                ):
                    try:
                        shutil.copy2(source_file_path, replica_file_path)
                        self.logger.info(
                            f"Copied/updated: {source_file_path} to {replica_file_path}"
                        )
                    except (OSError, shutil.Error) as err:
                        self.logger.error(
                            f"Failed to copy/update {source_file_path}. Error: {err}"
                        )

    def _remove_extras(self):
        """Removes files and directories from the replica folder that no longer exist in the source folder."""
        for root, dirs, files in os.walk(self.replica_folder_path, topdown=False):
            root_path = Path(root)
            source_root_path = self._get_source_root_path(root_path)

            if source_root_path is None:
                self.logger.error(f"Skipping sync: Invalid replica path: {root_path}")
                continue

            for file in files:
                replica_file_path = root_path / file
                source_file_path = source_root_path / file

                if not source_file_path.exists():
                    try:
                        replica_file_path.unlink()
                        self.logger.info(f"Removed file: {replica_file_path}")
                    except OSError as err:
                        self.logger.error(
                            f"Failed to remove file {replica_file_path}. Error: {err}"
                        )

            for dir in dirs:
                replica_dir_path = root_path / dir
                source_dir_path = source_root_path / dir

                if not source_dir_path.exists():
                    try:
                        shutil.rmtree(replica_dir_path)
                        self.logger.info(f"Removed directory: {replica_dir_path}")
                    except OSError as err:
                        self.logger.error(
                            f"Failed to remove directory {replica_dir_path}. Error: {err}"
                        )

    def _sha256_check(self, file_path):
        """Computes the SHA-256 hash of the given file.

        Args:
            file_path (str): Absolute path to the file for hash calculation

        Returns:
            str: The SHA-256 hexadecimal digest of the file
        """
        hash_sha256 = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except OSError as err:
            self.logger.error(
                f"Failed to read file for hashing: {file_path}. Error: {err}"
            )
            return None

    def _file_changed(self, source_file, replica_file):
        """Compares two files to determine if their contents differ using SHA-256 hashing.

        - If the source file cannot be read, syncing is skipped to avoid data loss.
        - If the replica cannot be read, it needs to be updated.

        Args:
            source_file (Path): Path to the source file
            replica_file (Path): Path to the replica file

        Returns:
            bool: True if the files differ"""
        source_hash = self._sha256_check(source_file)
        replica_hash = self._sha256_check(replica_file)

        if source_hash is None:
            self.logger.error(
                f"Skipping sync: failed to read source file {source_file}"
            )
            return False  # Do not sync if source is unreadable

        if replica_hash is None:
            self.logger.warning(
                f"Starting sync: failed to read replica file {replica_file}"
            )
            return True  # Trigger sync to recreate it

        return source_hash != replica_hash

    def _get_replica_root_path(self, source_root_path):
        """
        Computes the corresponding replica directory for given source directory.

        Args:
            source_root_path (Path): Path inside the source directory

        Returns:
            Path: Corresponding path inside the replica folder
        """
        try:
            source_rel_path = source_root_path.relative_to(self.source_folder_path)
            return self.replica_folder_path / source_rel_path
        except ValueError as err:
            self.logger.error(
                f"Invalid source path: {source_root_path} is not under source folder. Error: {err}"
            )
            return None

    def _get_source_root_path(self, replica_root_path: Path) -> Path:
        """
        Computes the corresponding source directory for a given replica directory.

        Args:
            replica_root_path (Path): Path inside the replica directory

        Returns:
            Path: Corresponding path inside the source folder
        """
        try:
            replica_rel_path = replica_root_path.relative_to(self.replica_folder_path)
            return self.source_folder_path / replica_rel_path
        except ValueError as err:
            self.logger.error(
                f"Invalid replica path: {replica_root_path} is not under replica folder. Error: {err}"
            )
            return None


def main():
    # Parse arguments
    parser = CLIParser()
    sync_config = parser.load_config()

    # Configure logger
    logger = LoggerConfigurator(sync_config.log_file_path).setup_logger()

    # Configure synchronization
    sync_task = SynchronizeFiles(
        sync_config.sync_interval,
        sync_config.sync_numbers,
        sync_config.source_folder_path,
        sync_config.replica_folder_path,
        logger,
    )
    # Start synchronization
    sync_task.run()


if __name__ == "__main__":
    main()
