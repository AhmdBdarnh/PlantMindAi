"""
recover_growth.py — Download all images from S3 captures/ into local captures/<day>/ folders.
Run from Backend/: python recover_growth.py
"""
from dotenv import load_dotenv
load_dotenv()

import os
import boto3

S3_BUCKET = os.environ.get('AWS_S3_BUCKET', 'plant-mindai')
S3_REGION = os.environ.get('AWS_REGION',    'eu-west-1')
S3_PREFIX = 'captures/'

LOCAL_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures')
IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}

print("=" * 55)
print("Downloading images from S3 captures/ ...")
print(f"Saving to: {LOCAL_ROOT}")
print("=" * 55)

s3 = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
)

paginator  = s3.get_paginator('list_objects_v2')
all_objects = []
for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
    all_objects.extend(page.get('Contents', []))

if not all_objects:
    print("No objects found under captures/ in S3.")
else:
    print(f"Found {len(all_objects)} object(s) in S3.\n")
    downloaded = 0
    skipped    = 0

    for obj in all_objects:
        s3_key   = obj['Key']             # e.g. captures/cam1_20260428_225911.jpg
        filename = s3_key.split('/')[-1]  # e.g. cam1_20260428_225911.jpg

        # Skip empty folder keys
        if not filename:
            continue

        # Skip non-image files
        ext = os.path.splitext(filename)[1].lower()
        if ext not in IMAGE_EXTS:
            continue

        # Extract day from filename: cam1_YYYYMMDD_HHMMSS.jpg → DD
        parts = filename.split('_')
        if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
            day = parts[1][6:8]           # e.g. "28" from "20260428"
        else:
            day = obj['LastModified'].strftime('%d')  # fallback: use S3 date

        day_folder = os.path.join(LOCAL_ROOT, day)
        os.makedirs(day_folder, exist_ok=True)

        local_path = os.path.join(day_folder, filename)

        if os.path.exists(local_path):
            print(f"  SKIP  {filename}  (already exists)")
            skipped += 1
            continue

        try:
            s3.download_file(S3_BUCKET, s3_key, local_path)
            print(f"  OK    {filename}  → captures/{day}/")
            downloaded += 1
        except Exception as e:
            print(f"  ERROR {filename}: {e}")

    print(f"\nDownload complete — {downloaded} downloaded, {skipped} skipped.")
    print(f"Images saved under: {LOCAL_ROOT}")
