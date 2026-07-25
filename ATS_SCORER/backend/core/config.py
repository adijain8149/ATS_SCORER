import os
from pathlib import Path
try :
    from dotenv import load_dotenv
    load_dotenv()
    root_env = Path(__file__).resolve().parent.parent.parent.parent / '.env'
    if root_env.exists():
        load_dotenv(dotenv_path=root_env)
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
APP_TITLE = 'ATS RESUME ANALYZER API'
APP_VERSION = '1.0.0'
API_TITLE = APP_TITLE
API_VERSION = APP_VERSION
APP_DESCRIPTION = 'analyse resumes against job description using nlp + ml'
ALLOWED_ORIGINS = [ 
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*"
]
# file
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Supported MIME types and their short names
SUPPORTED_MIME_TYPES = {
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx'
}

SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx'}

SPACY_MODEL_PRIMARY = "en_core_web_md"  # better accuracy
SPACY_MODEL_SECONDARY = "en_core_web_sm"
SENTENCE_TRANSFORMER_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
SCORE_WEIGHTS = {
    "formatting":25 , "Keywords":25,"content":25,"skill_validation":15,"ats_compatibility":15
}
JD_KEYWORD_WEIGHT = 0.6
JD_SEMANTIC_WEIGHT = 0.4