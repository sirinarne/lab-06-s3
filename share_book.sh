#!/bin/bash
set -euo pipefail


# Check that all three arguments were provided
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <book_url> <bucket_name> <expiration_seconds>"
    exit 1
fi

# Read command-line arguments
BOOK_URL="$1"
BUCKET="$2"
EXPIRATION="$3"

# Get the book filename from the URL
FILENAME="${BOOK_URL##*/}"

# Create the local books directory
mkdir -p books

# Download the book
echo "Downloading $FILENAME..."
curl -fL "$BOOK_URL" -o "books/$FILENAME"

# Check whether the bucket already exists
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    # Create a new private bucket
    echo "Creating bucket $BUCKET..."
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi

# Upload the book without making it public
echo "Uploading $FILENAME..."
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Generate and print a presigned URL
echo "Presigned URL:"
aws s3 presign "s3://$BUCKET/$FILENAME" \
    --expires-in "$EXPIRATION"


