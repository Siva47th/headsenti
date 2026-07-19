import os
from pathlib import Path
import psycopg2

def load_dotenv():
    # Find .env in current or parent directory
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
        
    if env_path.exists():
        print(f"Loading environment from {env_path.resolve()}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")
    else:
        print("No .env file found. Relying on system environment variables.")

# Load environment variables on import
load_dotenv()

def get_db_connection():
    db_user = os.getenv("DB_USER", "newsuser")
    db_password = os.getenv("DB_PASSWORD", "newspass")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "news_pipeline")
    
    print(f"Connecting to database {db_name} on {db_host}:{db_port} as {db_user}...")
    return psycopg2.connect(
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        database=db_name
    )
