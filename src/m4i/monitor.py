import os
import time
import psutil
import csv
from datetime import datetime
import argparse


def aggregate_process_usage(process_name: str, interval=0.1):
    """
    Calculate the total memory (in GB) and the total use of the CPU (in percentage)
    of all processes with name equal to 'Process_name'.
    """
    total_memory_usage = 0
    total_cpu_usage = 0.0
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            if proc.info["name"].startswith(process_name):
                total_memory_usage += proc.info["memory_info"].rss
                total_cpu_usage += proc.cpu_percent(interval=interval)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return total_memory_usage, total_cpu_usage


def monitor_process(
    process_name: str = "python",
    interval: float = 1.0,
    output_file: str = None,
    directory: str = ".",
):
    """
    Constantly monitor the use of memory and CPU for the specified process,
    writing the data in a CSV file. If 'Output_file' is not specified, the name
    of the file is generated as '<process_name>_<data>.csv' and saved in the specified folder.

    :param process_name: Name of the process to be monitored.
    :param interval: Interval in seconds between one writing and another.
    :param output_file: Name of the CSV file to write the data (optional).
    :param directory: Folder in which to memorize the file (default: ".").
    """
    if output_file is None:
        output_file = f"{process_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

    output_file_path = os.path.join(directory, output_file)
    header = ["Timestamp", "Process", "Memory", "CPU"]
    os.makedirs(directory, exist_ok=True)
    file_exists = os.path.exists(output_file_path)

    try:
        while True:
            t = time.time()
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            memory_usage, cpu_usage = aggregate_process_usage(process_name, interval=0.1)
            with open(output_file_path, mode="a", newline="") as csv_file:
                writer = csv.writer(csv_file)
                if not file_exists:
                    writer.writerow(header)
                file_exists = True
                writer.writerow(
                    [
                        timestamp,
                        process_name,
                        round(memory_usage / 1024 / 1024, 1),
                        cpu_usage,
                    ]
                )
                csv_file.flush()  # He immediately writes on a record.
            time.sleep(max(0, interval - (time.time() - t)))
    except KeyboardInterrupt:
        print("\nInterrupted monitoring.")
    except Exception as e:
        print(f"Unexpected error:{e}")


def run_from_command_line():
    """
    Interface function for the use of command line.
    """
    parser = argparse.ArgumentParser(description="Monitor the use of memory and CPU for specific processes.")
    parser.add_argument(
        "process_name",
        nargs="?",
        default="python",
        help="Name of the process to be monitored (default: 'Python').",
    )
    parser.add_argument(
        "interval",
        nargs="?",
        type=float,
        default=1,
        help="Writing interval in seconds (default: 1).",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default=None,
        help="Name of the Output CSV file (default: automatically generated).",
    )
    parser.add_argument(
        "--directory",
        type=str,
        default=".",
        help="Folder in which to store the CSV file (default: '.').",
    )
    args = parser.parse_args()

    monitor_process(args.process_name, args.interval, args.output_file, args.directory)


if __name__ == "__main__":
    run_from_command_line()
