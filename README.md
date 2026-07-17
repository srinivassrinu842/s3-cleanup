# S3 Cleanup & Maintenance Tool

A high-performance, dynamic S3 maintenance CLI utility designed to scan, estimate, sort, and batch-delete objects from large S3 buckets (such as Huawei OceanStor, MinIO, Ceph, or AWS S3). 

This tool is optimized for massive buckets (millions of keys, e.g., Loki chunk stores) where standard linear listing is slow or times out. It uses **dynamic prefix discovery**, **multi-threading**, and **bulk API operations** to guarantee safe and fast execution.

---

## Repository Structure

The project conforms to standard Python packaging layouts:
```text
s3_cleanup/
├── setup.py               # Package metadata and entry points
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Testing, formatting, and linting tools
├── README.md              # Documentation
├── src/                   # Package source code
│   └── s3_cleanup/
│       ├── __init__.py    # Versioning
│       └── main.py        # CLI entry point logic
└── tests/                 # Unit tests
    ├── __init__.py
    └── test_main.py       # Test cases
```

---

## Prerequisites & Installation

Ensure you have Python 3.9+ and credentials configured (e.g. standard environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).

### 1. Create a Virtual Environment (Optional but recommended)
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

* **For general use**:
  ```bash
  pip install -r requirements.txt
  ```
* **For development and testing**:
  ```bash
  pip install -r requirements-dev.txt
  ```

### 3. Install the Command Line Executable
Run the setup script in editable mode to register the `s3-cleanup` CLI shortcut globally inside your active virtual environment:
```bash
pip install -e .
```
Verify the installation works:
```bash
s3-cleanup --help
```

---

## Subcommands & Options

You can invoke the utility using either `s3-cleanup` (if installed via pip) or directly via python:
```bash
# Executable shortcut
s3-cleanup [command] [args]

# Direct python runner
python3 src/s3_cleanup/main.py [command] [args]
```

### 1. `usage` (Bucket Storage Estimation)
Quickly calculates the object count and cumulative storage size of the entire bucket or a specific subfolder.

```bash
# Command line syntax:
s3-cleanup usage -e <endpoint> -b <bucket> -p <folder_prefix> -w <workers>

# Interactive mode (will prompt you for missing options):
s3-cleanup usage
```

### 2. `scan` (Filter and Export Metadata)
Discovers and lists all files older than a specified YYYY-MM-DD cutoff date. Generates a metadata list file containing `LastModified | Size (MB) | Object Key`.

```bash
# Run scan filtering files older than July 1, 2026:
s3-cleanup scan -e "https://oceanstor.endpoint" -b "my-bucket" -p "network/" -c "2026-07-01" -o "old_files_list.txt" -w 16
```

*   `-c, --cutoff`: The date threshold (default: **today's date**).
*   `-o, --output`: Where to save the scanned metadata (default: `old_files_list.txt`).
*   `-w, --workers`: Maximum parallel listing workers (default: `16`).

### 3. `sort` (Offline Sort)
Sorts the generated text list file by either `date` (chronological) or `size` (numerical) without talking to S3.

```bash
# Sort by Date (Oldest first):
s3-cleanup sort -i old_files_list.txt -o date_sorted.txt -by date

# Sort by Size (Largest first):
s3-cleanup sort -i old_files_list.txt -o size_sorted.txt -by size --reverse
```

### 4. `summary` (Local Summary Report)
Reads any list file generated during the `scan` phase and prints a quick summary showing total count and size (in MB, GB, and TB) offline.

```bash
s3-cleanup summary -i date_sorted.txt
```

### 5. `delete` (Targeted Cleanup)
Safely deletes objects listed in your sorted file, starting from the top, up to a specified storage threshold (in GB).

```bash
# Delete the oldest 100 GB of objects:
s3-cleanup delete -e "https://oceanstor.endpoint" -b "my-bucket" -i date_sorted.txt -l 100.0
```

*   `-l, --limit-gb`: Stop deleting once this cumulative limit is reached (default: `100.0` GB).
*   `--dry-run`: Pass this flag to simulate and calculate the exact files that would be deleted without executing the actual S3 delete requests.

---

## Code Quality & Testing

### Running Tests
To run unit tests locally:
```bash
# Using standard Python unittest
python3 -m unittest discover -s tests -p 'test_*.py'

# Using pytest
pytest tests/
```

### Formatting & Linting
The project uses `black` and `ruff` for code styling:
```bash
# Auto-format codebase
black src/ tests/

# Lint checks
ruff check src/ tests/
```
*(Note: Pushing code to GitHub triggers a CI workflow that automatically formats changes using Black and runs lint validation checks).*
