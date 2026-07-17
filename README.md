# S3 Cleanup & Maintenance Tool

A high-performance, dynamic S3 maintenance CLI utility designed to scan, estimate, sort, and batch-delete objects from large S3 buckets (such as Huawei OceanStor, MinIO, Ceph, or AWS S3). 

This tool is optimized for massive buckets (millions of keys, e.g., Loki chunk stores) where standard linear listing is slow or times out. It uses **dynamic prefix discovery**, **multi-threading**, and **bulk API operations** to guarantee safe and fast execution.

---

## Key Features

*   ⚡ **Dynamic Prefix Scanning**: Automatically discovers first-level folders using S3 `Delimiter='/'` before querying, allowing parallelization across subdirectories.
*   🚀 **Multi-threaded Listing**: Utilizes a Python `ThreadPoolExecutor` to download and scan chunks concurrently.
*   🗑️ **Fast Batch Deletions**: Deletes files in blocks of 1,000 objects per API call using S3 `delete_objects`.
*   💬 **Interactive Shell Prompts**: If any parameter is omitted from the CLI commands, the script prompts you interactively with sensible defaults.
*   📦 **Stand-alone Dependency**: Only requires `boto3`.

---

## Prerequisites

Ensure you have Python 3 and the AWS SDK (`boto3`) installed:

```bash
pip install boto3
```

Ensure your credentials or credentials profiles are set up via standard AWS environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or config files.

---

## Installation

1. Make the script executable:
   ```bash
   chmod +x s3_cleanup.py
   ```

2. Run the help command to confirm installation:
   ```bash
   ./s3_cleanup.py --help
   ```

---

## Commands & Subcommands

### 1. `usage` (Bucket Space Analysis)
Quickly calculates the object count and cumulative storage size of the entire bucket or a specific subfolder.

```bash
# Standard command-line syntax:
./s3_cleanup.py usage -e <endpoint> -b <bucket> -p <folder_prefix> -w <workers>

# Interactive mode (prompts for missing options):
./s3_cleanup.py usage
```

### 2. `scan` (Identify Old Files)
Discovers and lists all files older than a specified YYYY-MM-DD cutoff date. Generates a metadata list file containing `LastModified | Size (MB) | Object Key`.

```bash
# Run scan filtering files older than July 1, 2026:
./s3_cleanup.py scan -e "https://oceanstor.endpoint" -b "my-bucket" -p "network/" -c "2026-07-01" -o "old_files_list.txt" -w 16
```

*   `-c, --cutoff`: The date threshold. Defaults dynamically to **today's date**.
*   `-o, --output`: Where to save the scanned metadata (default: `old_files_list.txt`).
*   `-w, --workers`: Maximum parallel listing workers (default: `16`).

### 3. `sort` (Order Scan Output)
Sorts the generated text list file by either `date` (chronological) or `size` (numerical) without talking to S3.

```bash
# Sort by Date (Oldest first):
./s3_cleanup.py sort -i old_files_list.txt -o date_sorted.txt -by date

# Sort by Size (Largest first):
./s3_cleanup.py sort -i old_files_list.txt -o size_sorted.txt -by size --reverse
```

### 4. `summary` (Local Summary Report)
Reads any list file generated during the `scan` phase and prints a quick report showing total count and size (in MB, GB, and TB) offline.

```bash
./s3_cleanup.py summary -i date_sorted.txt
```

### 5. `delete` (Targeted Cleanup)
Safely deletes objects listed in your sorted file, starting from the top, up to a specified storage threshold (in GB).

```bash
# Delete the oldest 100 GB of objects:
./s3_cleanup.py delete -e "https://oceanstor.endpoint" -b "my-bucket" -i date_sorted.txt -l 100.0
```

*   `-l, --limit-gb`: Stop deleting once this cumulative limit is reached (default: `100.0` GB).
*   `--dry-run`: Pass this flag to simulate and calculate the exact files that would be deleted without executing the actual S3 delete requests.

---

## Workflow Example: Freeing up 100 GB

1. **Scan the bucket** for files older than July 1st, saving results to `network_files.txt`:
   ```bash
   ./s3_cleanup.py scan -e "https://oceanstor.endpoint" -b "my-bucket" -p "network/" -c "2026-07-01" -o "network_files.txt"
   ```
2. **Sort by Date** to put the oldest files at the top of the list:
   ```bash
   ./s3_cleanup.py sort -i network_files.txt -o sorted_by_date.txt -by date
   ```
3. **Verify the plan** using a dry run:
   ```bash
   ./s3_cleanup.py delete -e "https://oceanstor.endpoint" -b "my-bucket" -i sorted_by_date.txt -l 100 --dry-run
   ```
4. **Execute the deletion** (will prompt you with a final `yes/no` confirmation):
   ```bash
   ./s3_cleanup.py delete -e "https://oceanstor.endpoint" -b "my-bucket" -i sorted_by_date.txt -l 100
   ```
