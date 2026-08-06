import json
import math
import os
import threading
import time
import zoneinfo

from collections import deque
from datetime import datetime

BUFFER_DURATION_SECONDS = 30 * 60
SAMPLE_INTERVAL = 0.1            # 100 ms
MAX_BUFFER_SIZE = int(BUFFER_DURATION_SECONDS / SAMPLE_INTERVAL)

JSON_WRITE_INTERVAL = 30         # seconds


class ImuManager:

    def __init__(self, logger, ui=None):
        self.logger = logger
        self.ui = ui
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Circular RAM buffer
        self.samples = deque(maxlen=MAX_BUFFER_SIZE)

        # Statistics
        self.total_samples = 0

        self.last_write = time.time()

    # Timestamp helper
    def timestamp(self):
        return datetime.now(
            zoneinfo.ZoneInfo("Asia/Kolkata")
        ).isoformat()

    # JSON Writer
    def write_json(self):
        with self._lock:
            history = list(self.samples)

        with open("imu_history.json", "w") as fp:
            json.dump(history, fp, indent=4)

    # Main Recording API
    def record(self,ax, ay, az, gx, gy, gz):
        sample = {
            "timestamp": self.timestamp(),
            "epoch": time.time(),
        
            "ax": int(ax),
            "ay": int(ay),
            "az": int(az),
        
            "gx": int(gx),
            "gy": int(gy),
            "gz": int(gz)
        }

        with self._lock:
            self.samples.append(sample)
            self.total_samples += 1

        # Push to Web Dashboard
        if self.ui is not None:
            try:
                self.ui.send_message(
                    "imu_sample",
                    sample
                )
            except Exception:
                pass

    # APIs
    def get_latest_samples(
        self,
        count=200
    ):

        with self._lock:
            return list(self.samples)[-count:]

    ###########################################################

    def get_last_30_minutes(self):
        with self._lock:
            return list(self.samples)

    ###########################################################

    def get_statistics(self):
        with self._lock:
            if len(self.samples) == 0:
                return {
                    "sampleCount": 0
                }

            ax = [x["ax"] for x in self.samples]
            ay = [x["ay"] for x in self.samples]
            az = [x["az"] for x in self.samples]

            gx = [x["gx"] for x in self.samples]
            gy = [x["gy"] for x in self.samples]
            gz = [x["gz"] for x in self.samples]

        def stats(values):
            avg = sum(values) / len(values)
            rms = math.sqrt(
                sum(v * v for v in values) /
                len(values)
            )
            return {
                "min": min(values),
                "max": max(values),
                "avg": round(avg, 2),
                "rms": round(rms, 2)
            }

        return {
            "sampleCount": len(ax),
            "totalSamples": self.total_samples,
            "accelerometer": {
                "x": stats(ax),
                "y": stats(ay),
                "z": stats(az)
            },

            "gyroscope": {
                "x": stats(gx),
                "y": stats(gy),
                "z": stats(gz)
            }
        }

    ###########################################################

    def clear_history(self):
        with self._lock:
            self.samples.clear()
            self.total_samples = 0

        with open("imu_history.json", "w") as fp:
            json.dump([], fp, indent=4)

    # Background Worker
    def _worker(self):
        self.logger.info("ImuManager worker started.")
        while self._running:
            try:
                now = time.time()
                #
                # Flush RAM buffer to disk every 30 seconds
                if (now - self.last_write) >= JSON_WRITE_INTERVAL:
                    self.write_json()
                    self.last_write = now
                    self.logger.info(
                        f"IMU Buffer: {len(self.samples)}/{MAX_BUFFER_SIZE} "
                        f"(Total Samples: {self.total_samples})"
                    )

                # Sleep to avoid busy waiting
                time.sleep(1)
    
            except Exception as e:
                self.logger.exception(
                    f"ImuManager Worker Error: {e}"
                )
    
        # Flush remaining samples before exiting
        self.logger.info(
            "Writing remaining IMU samples before shutdown."
        )
    
        self.write_json()
    
        self.logger.info(
            "ImuManager worker stopped."
        )
    
    # Lifecycle
    def start(self):
        if self._running:
            return
    
        self.logger.info(
            "Starting ImuManager..."
        )

        # Fresh start
        self.clear_history()
        self.last_write = time.time()
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            name="ImuManager",
            daemon=True
        )
        self._thread.start()
    
    def stop(self):
        self.logger.info(
            "Stopping ImuManager..."
        )

        self._running = False
        if ( self._thread is not None and \
            threading.current_thread() != self._thread):
            self._thread.join()
    
        self._thread = None
    
        # Final write
        self.write_json()
    
        self.logger.info(
            "ImuManager stopped."
        )
    # Optional Export Helpers
    
    def export_json(self, filename):
        with self._lock:
            data = list(self.samples)
    
        with open(filename, "w") as fp:
            json.dump(data, fp, indent=4)
    
    ###########################################################
    
    def export_csv(self, filename):
        import csv
        with self._lock:
            data = list(self.samples)
        if len(data) == 0:
            return
    
        with open(filename, "w", newline="") as fp:
            writer = csv.writer(fp)
    
            writer.writerow([
                "timestamp",
                "ax",
                "ay",
                "az",
                "gx",
                "gy",
                "gz"
            ])
    
            for sample in data:
                writer.writerow([
                    sample["timestamp"],
    
                    sample["ax"],
                    sample["ay"],
                    sample["az"],
    
                    sample["gx"],
                    sample["gy"],
                    sample["gz"]
                ])
    
        self.logger.info(
            f"Exported {len(data)} IMU samples to {filename}"
        )
