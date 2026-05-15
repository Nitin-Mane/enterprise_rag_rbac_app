import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError, RepositoryNotFoundError


MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
TARGET = Path(__file__).resolve().parents[1] / "models" / "qwen2.5-0.5b-instruct"
MAX_ATTEMPTS = 3


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            snapshot_download(
                repo_id=MODEL_ID,
                local_dir=TARGET,
                allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "tokenizer.*", "*.py"],
            )
            print(f"Saved {MODEL_ID} to {TARGET}")
            return 0
        except RepositoryNotFoundError:
            print(f"Model repository was not found or requires authentication: {MODEL_ID}")
            return 2
        except LocalEntryNotFoundError as exc:
            if attempt == MAX_ATTEMPTS:
                print("Could not reach Hugging Face and no complete cached snapshot was found.")
                print(f"Target folder: {TARGET}")
                print(f"Reason: {exc}")
                print("The application will still run with its extractive fallback until the model is downloaded.")
                return 1
        except Exception as exc:
            if attempt == MAX_ATTEMPTS:
                print(f"Model download failed after {MAX_ATTEMPTS} attempts.")
                print(f"Target folder: {TARGET}")
                print(f"Reason: {exc}")
                print("The application will still run with its extractive fallback until the model is downloaded.")
                return 1

        wait_seconds = attempt * 5
        print(f"Download attempt {attempt} failed. Retrying in {wait_seconds} seconds...")
        time.sleep(wait_seconds)

    return 1


if __name__ == "__main__":
    sys.exit(main())
