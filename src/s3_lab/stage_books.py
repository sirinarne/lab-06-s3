
#!/usr/bin/env python3

import os
import sys
import time
import json
import logging
import boto3
import requests
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create S3 client
s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read command-line arguments for the book list, index, and bucket."""

    if len(sys.argv) < 4:
        logger.error(
            "Usage: python stage_books.py <list_file> <index_path> <bucket>"
        )
        sys.exit(1)

    list_file = sys.argv[1]
    index_path = sys.argv[2]
    bucket = sys.argv[3]

    logger.info("Command-line arguments parsed successfully")

    return list_file, index_path, bucket


def download_books(list_file, dest_dir):
    """Download books from a list of URLs into a local directory."""

    os.makedirs(dest_dir, exist_ok=True)
    downloaded_files = []

    # Read URLs from the list file
    try:
        with open(list_file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    except OSError as e:
        logger.error(f"Error reading book list: {e}")
        return downloaded_files

    # Download each book
    for url in urls:
        filename = os.path.basename(url)
        path = os.path.join(dest_dir, filename)

        # Skip files that already exist
        if os.path.exists(path):
            logger.info(f"Skipping {filename}, already downloaded")
            downloaded_files.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(path, "wb") as f:
                f.write(response.content)

            downloaded_files.append(path)
            logger.info(f"Downloaded {filename}")

            # Pause between downloads
            time.sleep(1)

        except requests.RequestException as e:
            logger.error(f"Error downloading {url}: {e}")
        except OSError as e:
            logger.error(f"Error saving {filename}: {e}")

    return downloaded_files


def create_bucket(bucket):
    """Create an S3 bucket if it does not already exist."""

    # Check if bucket already exists
    try:
        s3.head_bucket(Bucket=bucket)
        logger.info(f"Bucket {bucket} already exists")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        # Only attempt creation if the bucket was not found
        if error_code not in ("404", "NoSuchBucket", "NotFound"):
            logger.error(f"Error checking bucket {bucket}: {e}")
            return False

    # Create the bucket
    try:
        s3.create_bucket(Bucket=bucket)
        logger.info(f"Created bucket {bucket}")
        return True

    except ClientError as e:
        logger.error(f"Error creating bucket {bucket}: {e}")
        return False


def make_public(bucket):
    """Make the bucket publicly readable."""

    try:
        # Turn off Block Public Access
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False
            }
        )

        # Create a public read-only bucket policy
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*"
                }
            ]
        }

        # Attach the policy
        s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(policy)
        )

        logger.info(f"Bucket {bucket} is publicly readable")
        return True

    except ClientError as e:
        logger.error(f"Error making bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload downloaded books to the S3 bucket."""

    uploaded_count = 0

    for path in file_paths:
        filename = os.path.basename(path)

        try:
            s3.upload_file(
                path,
                bucket,
                filename,
                ExtraArgs={
                    "ContentType": "text/plain; charset=utf-8"
                }
            )

            uploaded_count += 1
            logger.info(f"Uploaded {filename}")

        except (ClientError, OSError) as e:
            logger.error(f"Error uploading {filename}: {e}")

    return uploaded_count


def upload_index(bucket, index_path):
    """Upload the HTML index page to the S3 bucket."""

    if not os.path.exists(index_path):
        logger.error(f"Index file not found: {index_path}")
        return False

    try:
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            ExtraArgs={
                "ContentType": "text/html"
            }
        )

        logger.info("Uploaded index.html")
        return True

    except (ClientError, OSError) as e:
        logger.error(f"Error uploading index.html: {e}")
        return False


def main():
    """Download books, create a public bucket, and upload files."""

    # Read command-line arguments
    list_file, index_path, bucket = parse_args()

    # Download books
    file_paths = download_books(list_file, "books")

    if not file_paths:
        logger.error("No books downloaded")
        sys.exit(1)

    logger.info(f"Found {len(file_paths)} books")

    # Create bucket
    if not create_bucket(bucket):
        logger.error("Could not create bucket")
        sys.exit(1)

    # Make bucket public
    if not make_public(bucket):
        logger.error("Could not make bucket public")
        sys.exit(1)

    # Upload books
    uploaded_count = upload_files(bucket, file_paths)
    logger.info(f"Uploaded {uploaded_count} books")

    # Upload index page
    index_success = upload_index(bucket, index_path)

    if not index_success or uploaded_count != len(file_paths):
        logger.error("Some files failed to upload")
        sys.exit(1)

    # Display public URL
    url = f"https://{bucket}.s3.amazonaws.com/index.html"

    logger.info("Successfully staged books in S3")
    logger.info(f"Public index URL: {url}")


if __name__ == "__main__":
    main()

