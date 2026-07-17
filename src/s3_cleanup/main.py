#!/usr/bin/env python3
import argparse
import datetime
import concurrent.futures
import sys
import boto3

def get_s3_client(endpoint, region=None):
    return boto3.client('s3', endpoint_url=endpoint, region_name=region)

def get_required_arg(value, prompt_message, error_message):
    """
    Prompts the user interactively if a required value is missing.
    """
    if not value:
        try:
            value = input(prompt_message).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(1)
        if not value:
            print(f"Error: {error_message}")
            sys.exit(1)
    return value

def get_arg_with_default(value, prompt_message, default_value):
    """
    Prompts the user with a default option. If they press Enter, the default is used.
    """
    if value is None:
        try:
            user_input = input(f"{prompt_message} [default: {default_value}]: ").strip()
            if not user_input:
                value = default_value
            else:
                value = user_input
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(1)
    return value

# ==========================================
# SUBCOMMAND: SCAN (Dynamic Parallel Listing)
# ==========================================
def handle_scan(args):
    # Dynamic defaults for interactive prompts
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Prompt interactively for missing arguments
    endpoint = get_required_arg(args.endpoint, "Enter S3 Endpoint URL (e.g. https://ip:port): ", "Endpoint URL is required.")
    bucket = get_required_arg(args.bucket, "Enter S3 Bucket Name: ", "Bucket name is required.")
    prefix = get_arg_with_default(args.prefix, "Enter S3 Folder Prefix", "network/")
    cutoff_str = get_arg_with_default(args.cutoff, "Enter YYYY-MM-DD Cutoff Date", today_str)
    workers = int(get_arg_with_default(args.workers, "Enter number of parallel workers", "16"))
    
    # Ensure prefix ends with a slash if not empty
    if prefix and not prefix.endswith('/'):
        prefix += '/'

    s3_client = get_s3_client(endpoint)
    
    # 1. Discover subfolders
    print(f"\nDiscovering folders under s3://{bucket}/{prefix} ...")
    paginator = s3_client.get_paginator('list_objects_v2')
    folders = []
    try:
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter='/')
        for page in pages:
            for cp in page.get('CommonPrefixes', []):
                folders.append(cp['Prefix'])
    except Exception as e:
        print(f"Error accessing bucket '{bucket}': {str(e)}")
        sys.exit(1)
            
    if not folders:
        print(f"No subfolders found. Scanning '{prefix}' directly.")
        folders = [prefix]
    else:
        print(f"Found {len(folders)} dynamic folders to scan.")

    # Parse cutoff date
    cutoff = datetime.datetime.strptime(cutoff_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    print(f"Cutoff date set to: {cutoff_str} (scanning for objects modified before this date)")
    
    # Helper to scan a folder
    def scan_folder(folder_prefix):
        folder_paginator = s3_client.get_paginator('list_objects_v2')
        folder_pages = folder_paginator.paginate(Bucket=bucket, Prefix=folder_prefix)
        found_files = []
        try:
            for page in folder_pages:
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    if obj['LastModified'] < cutoff:
                        size_mb = obj['Size'] / (1024 * 1024)
                        found_files.append(
                            f"{obj['LastModified'].isoformat()} | {size_mb:.2f} MB | {obj['Key']}\n"
                        )
            print(f"Folder '{folder_prefix}' finished. Found {len(found_files)} matching files.")
            return found_files
        except Exception as e:
            print(f"Error scanning folder '{folder_prefix}': {str(e)}")
            return []

    # 2. Parallel Scan
    total_files = 0
    with open(args.output, "w") as f:
        f.write("LastModified | Size (MB) | Object Key\n")
        f.write("-" * 80 + "\n")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            results = executor.map(scan_folder, folders)
            for file_list in results:
                if file_list:
                    f.writelines(file_list)
                    total_files += len(file_list)
                    
    print(f"\nScan complete! Found {total_files} files. Saved to '{args.output}'.")

# ==========================================
# SUBCOMMAND: BUCKET USAGE (Fast Size Check)
# ==========================================
def handle_usage(args):
    endpoint = get_required_arg(args.endpoint, "Enter S3 Endpoint URL (e.g. https://ip:port): ", "Endpoint URL is required.")
    bucket = get_required_arg(args.bucket, "Enter S3 Bucket Name: ", "Bucket name is required.")
    prefix = get_arg_with_default(args.prefix, "Enter S3 Folder Prefix (leave blank for entire bucket)", "")
    workers = int(get_arg_with_default(args.workers, "Enter number of parallel workers", "16"))

    s3_client = get_s3_client(endpoint)
    
    print(f"\nDiscovering folders under s3://{bucket}/{prefix} ...")
    paginator = s3_client.get_paginator('list_objects_v2')
    folders = []
    
    try:
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter='/')
        for page in pages:
            for cp in page.get('CommonPrefixes', []):
                folders.append(cp['Prefix'])
    except Exception as e:
        print(f"Error accessing bucket '{bucket}': {str(e)}")
        sys.exit(1)

    if not folders:
        folders = [prefix]
    else:
        print(f"Found {len(folders)} dynamic folders. Querying size in parallel...")

    def get_folder_usage(folder_prefix):
        folder_paginator = s3_client.get_paginator('list_objects_v2')
        folder_pages = folder_paginator.paginate(Bucket=bucket, Prefix=folder_prefix)
        count = 0
        size_bytes = 0
        try:
            for page in folder_pages:
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    count += 1
                    size_bytes += obj['Size']
            return count, size_bytes
        except Exception as e:
            print(f"Error counting size for folder '{folder_prefix}': {str(e)}")
            return 0, 0

    total_count = 0
    total_size_bytes = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(get_folder_usage, folders)
        for count, size_bytes in results:
            total_count += count
            total_size_bytes += size_bytes

    total_mb = total_size_bytes / (1024 * 1024)
    total_gb = total_mb / 1024.0
    total_tb = total_gb / 1024.0

    print('=' * 50)
    print(f"Bucket Usage: s3://{bucket}/{prefix}")
    print('=' * 50)
    print(f"Total Objects: {total_count:,}")
    print(f"Total Size:    {total_mb:,.2f} MB")
    print(f"               {total_gb:,.2f} GB")
    print(f"               {total_tb:,.2f} TB")
    print('=' * 50)

# ==========================================
# SUBCOMMAND: SORT
# ==========================================
def parse_list_file(filename):
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found. Please run 'scan' first.")
        sys.exit(1)
        return [], []
        
    if len(lines) < 2:
        print("Empty or invalid file.")
        sys.exit(1)
        
    header = lines[:2]
    data = []
    for line in lines[2:]:
        if '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 3:
            continue
        data.append({
            'date': parts[0].strip(),
            'size': float(parts[1].replace('MB', '').strip()),
            'key': parts[2].strip(),
            'raw': line
        })
    return header, data

def handle_sort(args):
    header, data = parse_list_file(args.input)
    
    if args.by == 'date':
        data.sort(key=lambda x: x['date'], reverse=args.reverse)
    elif args.by == 'size':
        data.sort(key=lambda x: x['size'], reverse=args.reverse)
        
    with open(args.output, "w") as f:
        f.writelines(header)
        f.writelines([item['raw'] for item in data])
        
    print(f"Sorted file saved to '{args.output}' (sorted by {args.by}, reverse={args.reverse})")

# ==========================================
# SUBCOMMAND: SUMMARY
# ==========================================
def handle_summary(args):
    _, data = parse_list_file(args.input)
    total_mb = sum(item['size'] for item in data)
    total_gb = total_mb / 1024.0
    total_tb = total_gb / 1024.0
    
    print('=' * 50)
    print(f"Summary of {args.input}")
    print('=' * 50)
    print(f"Total Files: {len(data):,}")
    print(f"Total Size:  {total_mb:,.2f} MB")
    print(f"             {total_gb:,.2f} GB")
    print(f"             {total_tb:,.2f} TB")
    print('=' * 50)

# ==========================================
# SUBCOMMAND: DELETE
# ==========================================
def handle_delete(args):
    # Prompt interactively if required args are missing
    endpoint = get_required_arg(args.endpoint, "Enter S3 Endpoint URL (e.g. https://ip:port): ", "Endpoint URL is required.")
    bucket = get_required_arg(args.bucket, "Enter S3 Bucket Name: ", "Bucket name is required.")
    
    header, data = parse_list_file(args.input)
    s3_client = get_s3_client(endpoint)
    
    # Sort files by date (oldest first) to ensure clean deletion order
    data.sort(key=lambda x: x['date'])
    
    target_mb = args.limit_gb * 1024.0
    cumulative_size_mb = 0.0
    selected_keys = []
    
    for item in data:
        if cumulative_size_mb >= target_mb:
            break
        selected_keys.append({'Key': item['key']})
        cumulative_size_mb += item['size']
        
    actual_gb = cumulative_size_mb / 1024.0
    
    if not selected_keys:
        print("No files to delete.")
        return
        
    print(f"\nSelected {len(selected_keys):,} files totaling {actual_gb:.2f} GB for deletion.")
    
    if args.dry_run:
        print("[DRY RUN] No files were deleted.")
        return
        
    confirm = input(f"Are you sure you want to permanently delete these files from '{bucket}'? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Deletion canceled.")
        return
        
    batch_size = 1000
    deleted_count = 0
    for i in range(0, len(selected_keys), batch_size):
        batch = selected_keys[i:i + batch_size]
        try:
            s3_client.delete_objects(
                Bucket=bucket,
                Delete={'Objects': batch, 'Quiet': True}
            )
            deleted_count += len(batch)
            if deleted_count % 50000 == 0 or deleted_count == len(selected_keys):
                print(f"Deleted {deleted_count:,} / {len(selected_keys):,} files...")
        except Exception as e:
            print(f"Error at index {i}: {str(e)}")
            
    print(f"\nDone! Successfully deleted {deleted_count:,} files ({actual_gb:.2f} GB).")

# ==========================================
# MAIN ENTRYPOINT
# ==========================================
def main():
    parser = argparse.ArgumentParser(
        description="S3 Cleanup and Maintenance Utility Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # ------------------
    # Scan parser
    # ------------------
    scan_parser = subparsers.add_parser("scan", help="Scan S3 prefix dynamically and generate list")
    scan_parser.add_argument("-e", "--endpoint", default=None, help="S3 Endpoint URL (e.g. https://oceanstor.ip:port)")
    scan_parser.add_argument("-b", "--bucket", default=None, help="S3 Bucket name")
    scan_parser.add_argument("-p", "--prefix", default=None, help="Target directory prefix (e.g. 'network/')")
    scan_parser.add_argument("-c", "--cutoff", default=None, help="YYYY-MM-DD date filter (older than this date)")
    scan_parser.add_argument("-o", "--output", default="old_files_list.txt", help="Output file path")
    scan_parser.add_argument("-w", "--workers", default=None, help="Number of concurrent listing workers")
    
    # ------------------
    # Usage parser
    # ------------------
    usage_parser = subparsers.add_parser("usage", help="Get fast estimate of total bucket / prefix usage")
    usage_parser.add_argument("-e", "--endpoint", default=None, help="S3 Endpoint URL")
    usage_parser.add_argument("-b", "--bucket", default=None, help="S3 Bucket name")
    usage_parser.add_argument("-p", "--prefix", default=None, help="Folder prefix (blank for entire bucket)")
    usage_parser.add_argument("-w", "--workers", default=None, help="Number of parallel workers")

    # ------------------
    # Sort parser
    # ------------------
    sort_parser = subparsers.add_parser("sort", help="Sort the list file")
    sort_parser.add_argument("-i", "--input", default="old_files_list.txt", help="Input file path")
    sort_parser.add_argument("-o", "--output", default="date_sorted_old_files.txt", help="Output file path")
    sort_parser.add_argument("-by", choices=["date", "size"], default="date", help="Field to sort by")
    sort_parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting (e.g. descending order)")
    
    # ------------------
    # Summary parser
    # ------------------
    summary_parser = subparsers.add_parser("summary", help="Print total size and count from list file")
    summary_parser.add_argument("-i", "--input", default="old_files_list.txt", help="Input list file path")
    
    # ------------------
    # Delete parser
    # ------------------
    delete_parser = subparsers.add_parser("delete", help="Perform batch deletion from list file")
    delete_parser.add_argument("-e", "--endpoint", default=None, help="S3 Endpoint URL (e.g. https://oceanstor.ip:port)")
    delete_parser.add_argument("-b", "--bucket", default=None, help="S3 Bucket name")
    delete_parser.add_argument("-i", "--input", default="old_files_list.txt", help="Input list file path")
    delete_parser.add_argument("-l", "--limit-gb", type=float, default=100.0, help="Amount of storage to clean up (in GB)")
    delete_parser.add_argument("--dry-run", action="store_true", help="Simulate deletion without executing it")

    args = parser.parse_args()
    
    if args.command == "scan":
        handle_scan(args)
    elif args.command == "usage":
        handle_usage(args)
    elif args.command == "sort":
        handle_sort(args)
    elif args.command == "summary":
        handle_summary(args)
    elif args.command == "delete":
        handle_delete(args)

if __name__ == "__main__":
    main()
