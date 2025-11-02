import psutil, os, time, threading, duckdb
from datetime import datetime
from typing import Optional, Callable

class ResourceMonitor:
    def __init__(
        self,
        db_file: str = "monitor.duckdb",
        interval: int = 5,
        batch_size: int = 12,
        anomaly_factor: float = 1.5,
        warmup_samples: int = 20,
        alpha: float = 0.2,
        alert_callback: Optional[Callable] = None
    ):
        # Validate alpha is between 0 and 1
        if not 0 < alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        
        self.db_file = db_file
        self.interval = interval
        self.batch_size = batch_size
        self.anomaly_factor = anomaly_factor
        self.warmup_samples = warmup_samples
        self.alpha = alpha
        self.alert_callback = alert_callback

        self.lock = threading.Lock()
        self.process = psutil.Process(os.getpid())
        self.buffer = []
        self.sample_count = 0
        self.thread = None
        self.conn = None
        self.running = False

        # Smoothed baselines
        self.smoothed_rss = None
        self.smoothed_cpu = None
        
        # Warmup data storage
        self.warmup_rss = []
        self.warmup_cpu = []

    def _init_db(self):
        if not self.conn:
            try:
                self.conn = duckdb.connect(self.db_file)
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    ts TIMESTAMP,
                    rss_mb DOUBLE,
                    cpu_pct DOUBLE,
                    abnormal BOOLEAN,
                    deviation_pct DOUBLE,
                    baseline_mb DOUBLE,
                    severity VARCHAR
                )
                """)
                self.conn.commit()
            except Exception as e:
                print(f"❌ Database initialization error: {e}")
                raise

    def _smooth(self, prev, new):
        """Exponential smoothing helper"""
        if prev is None:
            return new
        return self.alpha * new + (1 - self.alpha) * prev

    def _classify_severity(self, rss_mb, rss_ref, rss_delta):
        """Determine severity level for memory growth"""
        # Avoid division by zero
        if rss_ref == 0:
            return "normal"
            
        if rss_mb > rss_ref * 2 or rss_delta > 100:
            return "critical"
        elif rss_mb > rss_ref * 1.5 or rss_delta > 50:
            return "major"
        elif rss_mb > rss_ref * 1.2 or rss_delta > 20:
            return "minor"
        return "normal"

    def _flush_buffer(self):
        """Flush buffer to database with error handling"""
        if not self.buffer:
            return
            
        try:
            with self.lock:
                self.conn.executemany(
                    "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?)",
                    self.buffer
                )
                self.conn.commit()
            print(f"💾 Flushed {len(self.buffer)} samples to DuckDB")
            self.buffer = []
        except Exception as e:
            print(f"❌ Database flush error: {e}")

    def _loop(self):
        # Initialize CPU monitoring
        self.process.cpu_percent(interval=None)
        
        while self.running:
            try:
                mem = self.process.memory_info()
                rss_mb = mem.rss / (1024 * 1024)
                cpu_pct = self.process.cpu_percent(interval=None)
                
                # Handle negative CPU edge case
                cpu_pct = max(0.0, cpu_pct)

                abnormal = False
                deviation_pct = 0.0
                severity = "normal"
                baseline_val = None

                self.sample_count += 1

                if self.sample_count <= self.warmup_samples:
                    self.warmup_rss.append(rss_mb)
                    self.warmup_cpu.append(cpu_pct)
                    print(f"[WARMUP {self.sample_count}/{self.warmup_samples}] RSS={rss_mb:.2f} MB, CPU={cpu_pct:.2f}%")
                    
                    # Initialize baselines after warmup
                    if self.sample_count == self.warmup_samples:
                        self.smoothed_rss = sum(self.warmup_rss) / len(self.warmup_rss)
                        self.smoothed_cpu = sum(self.warmup_cpu) / len(self.warmup_cpu)
                        print(f"✅ Warmup complete. Baseline RSS={self.smoothed_rss:.2f} MB, CPU={self.smoothed_cpu:.2f}%")
                        # Free warmup memory
                        self.warmup_rss = []
                        self.warmup_cpu = []
                else:
                    # Update smoothed baselines
                    self.smoothed_rss = self._smooth(self.smoothed_rss, rss_mb)
                    self.smoothed_cpu = self._smooth(self.smoothed_cpu, cpu_pct)

                    rss_ref = self.smoothed_rss
                    cpu_ref = self.smoothed_cpu
                    baseline_val = rss_ref

                    rss_delta = rss_mb - rss_ref
                    cpu_delta = cpu_pct - cpu_ref
                    
                    rss_deviation_pct = 0.0
                    cpu_deviation_pct = 0.0
                    anomaly_type = None

                    # Memory anomaly detection (only upward drift)
                    if rss_delta > 0:
                        severity = self._classify_severity(rss_mb, rss_ref, rss_delta)
                        if severity != "normal":
                            abnormal = True
                            rss_deviation_pct = (rss_delta / rss_ref) * 100 if rss_ref > 0 else 0
                            anomaly_type = "memory"

                    # CPU anomaly detection
                    if cpu_ref > 0 and cpu_pct > cpu_ref * self.anomaly_factor:
                        abnormal = True
                        cpu_deviation_pct = (cpu_delta / cpu_ref) * 100
                        if severity == "normal":
                            severity = "minor"
                        if anomaly_type:
                            anomaly_type = "memory+cpu"
                        else:
                            anomaly_type = "cpu"
                    
                    # Use the higher deviation for overall metric
                    deviation_pct = max(rss_deviation_pct, cpu_deviation_pct)

                    # Buffer data
                    self.buffer.append([
                        datetime.utcnow(),
                        rss_mb, cpu_pct, abnormal, deviation_pct, baseline_val, severity
                    ])

                    # Flush buffer if needed
                    if len(self.buffer) >= self.batch_size:
                        self._flush_buffer()

                    # Logging and alerts
                    if abnormal:
                        if anomaly_type == "memory":
                            alert_msg = f"🚨 {severity.upper()} {anomaly_type} anomaly! RSS={rss_mb:.2f} MB (baseline {baseline_val:.2f} MB) | ΔMem={rss_deviation_pct:.1f}%"
                        elif anomaly_type == "cpu":
                            alert_msg = f"🚨 {severity.upper()} {anomaly_type} anomaly! CPU={cpu_pct:.2f}% (baseline {cpu_ref:.2f}%) | ΔCPU={cpu_deviation_pct:.1f}%"
                        else:
                            alert_msg = f"🚨 {severity.upper()} {anomaly_type} anomaly! RSS={rss_mb:.2f} MB | CPU={cpu_pct:.2f}% | ΔMem={rss_deviation_pct:.1f}% | ΔCPU={cpu_deviation_pct:.1f}%"
                        print(alert_msg)
                        
                        # Trigger callback if provided
                        if self.alert_callback:
                            try:
                                self.alert_callback(severity, rss_mb, cpu_pct, baseline_val, deviation_pct)
                            except Exception as e:
                                print(f"⚠️ Alert callback error: {e}")
                    else:
                        print(f"[OK] RSS={rss_mb:.2f} MB, CPU={cpu_pct:.2f}%")

            except Exception as e:
                print(f"❌ Monitoring error: {e}")
            
            time.sleep(self.interval)

    def start(self):
        """Start the resource monitor"""
        if self.running:
            print("⚠️ Monitor is already running")
            return
            
        self._init_db()
        self.running = True
        
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("✅ ResourceMonitor started.")

    def stop(self):
        """Stop the resource monitor gracefully"""
        if not self.running:
            print("⚠️ Monitor is not running")
            return
            
        print("🛑 Stopping ResourceMonitor...")
        self.running = False
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        
        # Flush remaining buffer
        if self.conn and self.buffer:
            self._flush_buffer()
            print(f"🛑 Flushed {len(self.buffer)} remaining samples before shutdown.")
        
        # Close database connection
        if self.conn:
            try:
                self.conn.close()
                print("🛑 Database connection closed.")
            except Exception as e:
                print(f"⚠️ Error closing database: {e}")
        
        print("🛑 ResourceMonitor stopped.")

    def query_metrics(self, limit: int = 100):
        """Query recent metrics from the database"""
        if not self.conn:
            self._init_db()
        
        try:
            result = self.conn.execute(f"""
                SELECT * FROM metrics 
                ORDER BY ts DESC 
                LIMIT {limit}
            """).fetchall()
            return result
        except Exception as e:
            print(f"❌ Query error: {e}")
            return []

    def query_anomalies(self, severity: Optional[str] = None, limit: int = 50):
        """Query anomalies, optionally filtered by severity"""
        if not self.conn:
            self._init_db()
        
        try:
            query = "SELECT * FROM metrics WHERE abnormal = true"
            if severity:
                query += f" AND severity = '{severity}'"
            query += f" ORDER BY ts DESC LIMIT {limit}"
            
            result = self.conn.execute(query).fetchall()
            return result
        except Exception as e:
            print(f"❌ Query error: {e}")
            return []

    def get_statistics(self):
        """Get summary statistics from collected metrics"""
        if not self.conn:
            self._init_db()
        
        try:
            stats = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_samples,
                    SUM(CASE WHEN abnormal THEN 1 ELSE 0 END) as anomaly_count,
                    AVG(rss_mb) as avg_rss,
                    MAX(rss_mb) as max_rss,
                    AVG(cpu_pct) as avg_cpu,
                    MAX(cpu_pct) as max_cpu
                FROM metrics
            """).fetchone()
            return stats
        except Exception as e:
            print(f"❌ Statistics error: {e}")
            return None