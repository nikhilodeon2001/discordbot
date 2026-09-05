"""One-time seed script: upload the Usable=True anatomy images from trivia_game_data.csv
to S3 under anatomy_images/<filename>, for Okra's Anatomy.

Static assets that never change once uploaded, so by default this SKIPS any filename
whose S3 key already exists (checked via head_object) rather than re-uploading -- use
--force to override that and always overwrite.

Usage:
    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \
        python3 scripts/upload_anatomy_images_to_s3.py \
        --csv ~/Desktop/bone_trivia_images/trivia_game_data.csv \
        --assets-dir ~/Desktop/bone_trivia_images/trivia_game_assets \
        --dry-run
"""
import argparse
import csv
import mimetypes
import os

import boto3
from botocore.exceptions import ClientError

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "anatomy_images/"
CONTENT_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="re-upload even if the S3 key already exists")
    args = parser.parse_args()

    # Dry-run needs no AWS credentials at all -- it only checks local files exist and
    # reports what *would* be uploaded, without ever calling S3.
    s3 = None
    if not args.dry_run:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("AWS_REGION", "us-east-2"),
        )

    with open(os.path.expanduser(args.csv), newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["Usable"] == "True"]

    assets_dir = os.path.expanduser(args.assets_dir)
    print(f"Loaded {len(rows)} usable rows from {args.csv}")

    uploaded = skipped_exists = missing = 0
    for row in rows:
        filename = row["Filename"]
        local_path = os.path.join(assets_dir, filename)
        s3_key = S3_PREFIX + filename

        if not os.path.exists(local_path):
            print(f"  MISSING local file: {local_path}")
            missing += 1
            continue

        ext = os.path.splitext(filename)[1].lower()
        content_type = CONTENT_TYPES.get(ext) or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if args.dry_run:
            print(f"  [dry-run] would upload {local_path} -> s3://{S3_BUCKET_NAME}/{s3_key} ({content_type})")
            uploaded += 1
            continue

        if not args.force:
            try:
                s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                skipped_exists += 1
                continue
            except ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise

        with open(local_path, "rb") as fh:
            s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=fh, ContentType=content_type)
        uploaded += 1

    print(f"\nUploaded: {uploaded}, already present: {skipped_exists}, "
          f"missing local files: {missing}, total usable rows: {len(rows)}")
    if missing:
        raise SystemExit(f"ERROR: {missing} usable rows have no local file -- fix before proceeding.")


if __name__ == "__main__":
    main()
