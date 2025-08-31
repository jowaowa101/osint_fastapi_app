import sys
from pathlib import Path

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from osint_fastapi_app.classifier import classify_text

sample_text = "I hate this group of people. They should be banned."

result = classify_text(sample_text)

print("Classification Result:")
print(result)
