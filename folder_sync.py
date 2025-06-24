import os
import logging
import argparse
import shutil
import hashlib
import time

from pathlib import Path
from dataclasses import dataclass

CHUNK_SIZE = 4096
CONSOLE_LOG_LEVEL = logging.INFO
FILE_LOG_LEVEL = logging.DEBUG


@dataclass
class Config:
    """Holds configuration settings parsed from command-line args.

    Attributes:
        source_folder_path (Path): Path to source folder
        replica_folder_path (Path): Path to replica folder
        sync_interval (int): Synchronization interval in seconds
        sync_numbers (int): Total number of synchronization runs
        log_file_path (Path): Path to log file (.log format)
    """

    source_folder_path: Path
    replica_folder_path: Path
    sync_interval: int
    sync_numbers: int
    log_file_path: Path


class CLIParser:
    """Reads the required arguments for the folder synchronization program and validate required paths (source and replica).

    Attributes:
        logger (logging.Logger): Logger for log events
    """

    def __init__(self, logger: logging.Logger):
        """Initializes the CLIParser

        Args:
            logger (logging.Logger): Logger for log events
        """
        self.logger = logger
        self.parser = argparse.ArgumentParser(
            description=(
                "A command-line tool for one-way folder synchronization.\n\n"
                "Creates a mirror of the source directory in the replica directory by:\n"
                "- Comparing files using SHA-256,\n"
                "- Copying new files,\n"
                "- Updating changed files,\n"
                "- Removing files no longer present in the source.\n\n"
                "Synchronization occurs at fixed time intervals and is repeated specified number of times."
            ),
            epilog=(
                "Example usage:\n"
                "  python sync.py /home/user/source /home/user/replica 60 10 sync.log\n\n"
                "Where:\n"
                "  /home/user/source   - Source folder to be monitored\n"
                "  /home/user/replica  - Replica folder to receive synchronized data\n"
                "  60                  - Synchronization interval in seconds\n"
                "  10                  - Total number of synchronization runs\n"
                "  sync.log            - Path to the log file"
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self._setup_arguments()

    def _setup_arguments(self) -> None:
        """Defines expected arguments.

        Args:
            source_folder_path (Path): Path to source folder
            replica_folder_path (Path): Path to replica folder
            sync_interval (int): Synchronization interval in seconds
            sync_numbers (int): Total number of synchronization runs
            log_file_path (Path): Path to log file (.log format)
        """
        self.parser.add_argument(
            "source_folder_path", type=Path, help="Path to source folder"
        )
        self.parser.add_argument(
            "replica_folder_path", type=Path, help="Path to replica folder"
        )
        self.parser.add_argument(
            "sync_interval",
            type=int,
            help="Synchronization interval in seconds",
        )
        self.parser.add_argument(
            "sync_numbers", type=int, help="Total number of synchronization runs"
        )
        self.parser.add_argument("log_file_path", type=Path, help="Path to log file")

    def _is_path_valid(self, path: Path) -> Path | None:
        """Resolves and validates a path.

        Args:
            path (Path): The path to validate and resolve

        Returns:
            Path: The resolved absolute Path if valid
            None: otherwise
        """
        try:
            return path.resolve(strict=True)
        except OSError as err:
            self.logger.error(f"OSError during path validation for {path}: {err}")
            return None

    def load_config(self) -> Config | None:
        """Parses the CLI arguments and returns them as Config dataclass.

        Returns:
            Config: Object containing all parsed arguments and resolved source and replica paths
            None: if parsing failed or if source or replica directories dont exist
        """
        try:
            raw_args = self.parser.parse_args()
            raw_args.source_folder_path = self._is_path_valid(
                raw_args.source_folder_path
            )
            raw_args.replica_folder_path = self._is_path_valid(
                raw_args.replica_folder_path
            )
            if None in (raw_args.source_folder_path, raw_args.replica_folder_path):
                return None

            return Config(**vars(raw_args))
        except argparse.ArgumentError as err:
            self.logger.error(f"Argument parsing error: {err}")
            return None
        except SystemExit as err:
            # for --help no need to log the error
            if err.code == 0:
                return None
            self.logger.error(
                f"Invalid command-line arguments or '--help' called. Error: {err}"
            )
            return None


class FileLogFormatter(logging.Formatter):
    """Custom log formatter for file log output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for file log output.

        Args:
            record (logging.LogRecord): Log record containing event information

        Returns:
            str: Formatted log string
        """

        timestamp = self.formatTime(record, self.datefmt)
        return f"{timestamp} {record.levelname} [{record.funcName}:{record.lineno}] {record.getMessage()}"


class ConsoleLogFormatter(logging.Formatter):
    """Custom log formatter for console log output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output.

        Args:
            record (logging.LogRecord): Log record containing event information

        Returns:
            str: Formatted log string
        """
        return f"[{self.formatTime(record)}] {record.levelname} {record.getMessage()}"


class LoggerConfigurator:
    """Configures logging to the log file and to the console.

    Attributes:
        logger_name (str): name of the logger (defaults to "folder_sync")
    """

    def __init__(self, logger_name: str = "folder_sync"):
        """Initializes the LoggerConfigurator.

        Args:
            logger_name (str): name of the logger (defaults to "folder_sync")
        """
        self.logger_name = logger_name

    def setup_logger(self) -> logging.Logger:
        """Configure the logger with file and console handlers.

        Returns:
            logger (logging.Logger): Configured logger object
        """

        logger = logging.getLogger(self.logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        return logger

    def setup_file_handler(
        self,
        logger: logging.Logger,
        file_log_path: Path,
    ) -> None:
        """Initializes and attaches a file log handler to the given logger.

        Args:
            logger (logging.Logger): logger object to which the file handler will be added
            file_log_path (Path): path to the log file
        """
        try:
            file_log_path = Path(file_log_path).resolve()
        except (ValueError, TypeError) as err:
            logger.warning(f"Invalid log file path. Error: {err}")
            logging.warning("Logging to file unavailable")
            logger.propagate = False
            return

        try:
            file_handler = logging.FileHandler(
                file_log_path, mode="w", encoding="utf-8"
            )
            file_handler.setFormatter(FileLogFormatter())
            file_handler.setLevel(FILE_LOG_LEVEL)
            logger.addHandler(file_handler)
        except OSError as err:
            logging.warning(f"Couldn't initialize file log handler. Error: {err}")
            logging.warning("Logging to file unavailable")
            logger.propagate = False
            return
        except (TypeError, NameError) as err:
            logging.warning(f"Couldn't set file log level. Error: {err}")
            logging.warning("Logging to file unavailable")
            logger.propagate = False
            return

    def setup_console_handler(self, logger: logging.Logger) -> None:
        """Initializes and attaches a console log handler to the given logger.

        Args:
            logger (logging.Logger): logger object to which the console handler will be added
        """
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ConsoleLogFormatter())
        try:
            console_handler.setLevel(CONSOLE_LOG_LEVEL)
        except (TypeError, NameError) as err:
            logging.warning(f"Couldn't set console log level. Error: {err}")
            logging.warning("Logging to console unavailable")
            logger.propagate = False
            return

        logger.addHandler(console_handler)


class SynchronizeFiles:
    """Performs one-way synchronization between given source and replica folders.

    Attributes:
        sync_interval (int): Interval in seconds between sync runs
        sync_numbers (int): Number of total sync cycles
        source_folder_path (Path): Absolute path to the source folder
        replica_folder_path (Path): Absolute path to the replica folder
        logger (logging.Logger): Logger for log events
    """

    def __init__(
        self,
        sync_interval: int,
        sync_numbers: int,
        source_folder_path: Path,
        replica_folder_path: Path,
        logger: logging.Logger,
    ):
        """Initializes the SynchronizeFiles

        Args:
            sync_interval (int): Interval in seconds between sync runs
            sync_numbers (int): Number of total sync cycles
            source_folder_path (Path): Absolute path to the source folder
            replica_folder_path (Path): Absolute path to the replica folder
            logger (logging.Logger): Logger for log events
        """
        self.sync_interval = sync_interval
        self.sync_numbers = sync_numbers
        self.logger = logger
        self.source_folder_path = source_folder_path
        self.replica_folder_path = replica_folder_path

    def start_sync_loop(self) -> None:
        """Executes sync process for specified number of times."""
        for i in range(self.sync_numbers):
            self.logger.info(f"Starting sync run {i + 1}/{self.sync_numbers}")
            self._sync_source_and_replica()
            self.logger.info(f"Finished sync run {i + 1}/{self.sync_numbers}")

            if i < self.sync_numbers - 1:  # prevent from sleeping at last iteration
                self.logger.debug(f"Sleeping for {self.sync_interval} seconds")
                time.sleep(self.sync_interval)

    def _sync_source_and_replica(self) -> None:
        """Performs single full sync which include adding, updating and removing files for source and replica."""
        self._update_replica_from_source()
        self._sync_removals()

    def _update_replica_from_source(self) -> None:
        """Copies new or updated files and directories from the source folder to the replica."""
        for root, _, files in os.walk(self.source_folder_path):
            root_path = Path(root)
            replica_root_path = self._get_relative_root_path(
                root_path, self.source_folder_path, self.replica_folder_path
            )

            if replica_root_path is None:
                self.logger.error(f"Skipping sync: Invalid source path {root_path}")
                continue

            if not self._ensure_directory_exists(replica_root_path):
                continue

            for file in files:
                self._sync_file(file, root_path, replica_root_path)

    def _sync_file(
        self, filename: str, source_root_path: Path, replica_root_path: Path
    ) -> None:
        """Synchronize single file from source to replica.

        Args:
            filename (str): Name of the file to synchronize
            source_root_path (Path): Path to the source directory containing the file
            replica_root_path (Path): Path to the replica directory where the file should be copied
        """
        source_file_path = source_root_path / filename
        replica_file_path = replica_root_path / filename

        if not replica_file_path.exists() or self._is_file_changed(
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

    def _sync_removals(self) -> None:
        """Removes files and directories from the replica folder that no longer exist in the source folder."""
        for root, _, files in os.walk(self.replica_folder_path, topdown=False):
            root_path = Path(root)
            source_root_path = self._get_relative_root_path(
                root_path, self.replica_folder_path, self.source_folder_path
            )

            if source_root_path is None:
                self.logger.error(f"Skipping sync: Invalid replica path: {root_path}")
                continue

            if self._is_directory_obsolete(source_root_path, root_path):
                continue

            for file in files:
                self._remove_obsolote_file(file, source_root_path, root_path)

    def _sha256_calculate(self, file_path: Path) -> str | None:
        """Computes the SHA-256 hash of the given file.

        Args:
            file_path (Path): Absolute path to the file for hash calculation

        Returns:
            str: The SHA-256 hexadecimal digest of the file
            None: if failed to read file for hashing
        """
        hash_sha256 = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except OSError as err:
            self.logger.error(
                f"Failed to read file for hashing: {file_path}. Error: {err}"
            )
            return None
        except TypeError as err:
            self.logger.error(f"Invalid input for chunk size. Error: {err}")
            return None

    def _get_relative_root_path(
        self, root_path: Path, base_folder_path: Path, target_base_path: Path
    ) -> Path | None:
        """Computes the corresponding target directory path for a given root path.
        Args:
            root_path (Path): Path inside the source or replica folder
            base_folder_path (Path): Base path from which the relative path should be derived
            target_base_path (Path): Base path to which the relative path will be appended

        Returns:
            Path: Corresponding path inside the target folder
            None: If the root_path is not under the base_folder_path
        """
        try:
            relative_path = root_path.relative_to(base_folder_path)
            return target_base_path / relative_path
        except ValueError as err:
            self.logger.error(
                f"Invalid replica path: {root_path} is not under base folder {base_folder_path}. Error: {err}"
            )
            return None

    def _remove_obsolote_file(
        self, filename: str, source_root_path: Path, replica_root_path: Path
    ) -> None:
        """Removes a file from the replica directory if it no longer exists in the source directory.

        Args:
            filename (str): Name of the file to check for obsolescence
            source_root_path (Path): Path to the source directory that should contain the file
            replica_root_path (Path): Path to the replica directory where the file currently exists
        """
        source_file_path = source_root_path / filename
        replica_file_path = replica_root_path / filename

        if not source_file_path.exists():
            try:
                replica_file_path.unlink()
                self.logger.info(f"Removed file: {replica_file_path}")
            except OSError as err:
                self.logger.error(
                    f"Failed to remove file {replica_file_path}. Error: {err}"
                )

    def _is_directory_obsolete(
        self, source_directory_path: Path, replica_directory_path: Path
    ) -> bool:
        """Removes directory from replica if it no longer exists in source.

        Args:
            replica_dir_path (Path): Path to the directory in replica
            source_dir_path (Path): Expected path in the source directory

        Returns:
            bool: True if directory was removed, False otherwise
        """
        if not source_directory_path.exists():
            try:
                shutil.rmtree(replica_directory_path)
                self.logger.info(f"Removed directory: {replica_directory_path}")
            except OSError as err:
                self.logger.error(
                    f"Failed to remove directory {replica_directory_path}. Error: {err}"
                )
                return False
        return True

    def _ensure_directory_exists(self, directory_path: Path) -> bool:
        """Checks if directory exists, and creates it if it doesn't.

        Args:
            directory_path (Path): The path to the directory to check or create.

        Returns:
            bool: True if the directory exists or was created successfully,
                False if creation failed
        """
        if not directory_path.exists():
            try:
                directory_path.mkdir(parents=True)
                self.logger.info(f"Created directory: {directory_path}")
            except OSError as err:
                self.logger.error(
                    f"Failed to create directory {directory_path}. Error: {err}"
                )
                return False
        return True

    def _is_file_changed(self, source_file: Path, replica_file: Path) -> bool:
        """Compares two files to determine if their contents differ using SHA-256 hashing.

        - If the source file cannot be read, syncing is skipped to avoid data loss.
        - If the replica cannot be read, it needs to be updated.

        Args:
            source_file (Path): Path to the source file,
            replica_file (Path): Path to the replica file

        Returns:
            bool: True if the files differ or failed to read replica file,
                False if the files don't differ or failed to read source file
        """
        source_hash = self._sha256_calculate(source_file)
        replica_hash = self._sha256_calculate(replica_file)

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
        self.logger.info(
            f"SHA256 calculated correctly for both files: {source_file.stem}, {replica_file.stem}"
        )
        return source_hash != replica_hash


def main():
    # Configure logger
    logger_config = LoggerConfigurator()
    logger = logger_config.setup_logger()
    logger_config.setup_console_handler(logger)

    # Parse arguments
    parser = CLIParser(logger)
    sync_config = parser.load_config()

    if not sync_config:
        return

    # Configure logger file handler
    logger_config.setup_file_handler(logger, sync_config.log_file_path)

    # Configure synchronization
    sync_task = SynchronizeFiles(
        sync_config.sync_interval,
        sync_config.sync_numbers,
        sync_config.source_folder_path,
        sync_config.replica_folder_path,
        logger,
    )
    # Start synchronization
    sync_task.start_sync_loop()


if __name__ == "__main__":
    main()
