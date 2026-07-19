import time
import subprocess
import sys
from datetime import datetime

def run_step(script_name):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running {script_name}...")
    
    # Use the same python executable running the scheduler
    python_exe = sys.executable
    result = subprocess.run([python_exe, f"src/{script_name}"], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] running {script_name}:")
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)
        return False
        
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUCCESS] {script_name} completed successfully.")
    if result.stdout:
        print("Output:\n" + result.stdout)
    return True

def run_pipeline():
    print(f"\n==================================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting pipeline execution...")
    print(f"==================================================")
    
    if not run_step("scraper.py"):
        print("Pipeline aborted at scraper step.")
        return
        
    if not run_step("transform.py"):
        print("Pipeline aborted at transform step.")
        return
        
    if not run_step("dq_checks.py"):
        print("Pipeline aborted at data quality check step.")
        return
        
    if not run_step("load.py"):
        print("Pipeline aborted at loading step.")
        return
        
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUCCESS] Pipeline run completed successfully!\n")

def main():
    print("==================================================")
    print("   News Sentiment Pipeline Scheduler Active")
    print("==================================================")
    print("Running initial test run...")
    run_pipeline()
    
    # Interval: 6 hours (21,600 seconds)
    interval = 6 * 60 * 60
    
    while True:
        try:
            next_run_time = datetime.fromtimestamp(time.time() + interval).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Sleeping... Next scheduled run will trigger at: {next_run_time}\n")
            time.sleep(interval)
            run_pipeline()
        except KeyboardInterrupt:
            print("\nScheduler stopped by user.")
            break
        except Exception as e:
            print(f"Scheduler encountered an unexpected error: {e}")
            time.sleep(60) # Wait a minute before retrying

if __name__ == '__main__':
    main()
