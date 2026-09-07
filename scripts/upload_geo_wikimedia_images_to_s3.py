"""One-time seed script: upload the Wikimedia "on the globe" country locator images
(downloaded as <alpha2>.png) to S3 under geo_maps_wikimedia/<alpha2>.png, as a second
image option per country for the World Atlas minigame (used alongside the existing
Geography images already in trivia_questions).

Static assets that never change once uploaded, so by default this SKIPS any filename
whose S3 key already exists (checked via head_object) rather than re-uploading -- use
--force to override that and always overwrite.

Usage:
    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \
        python3 scripts/upload_geo_wikimedia_images_to_s3.py \
        --assets-dir /path/to/wikimedia_images \
        --dry-run
"""
import argparse
import os

import boto3
from botocore.exceptions import ClientError

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "geo_maps_wikimedia/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="re-upload even if the S3 key already exists")
    args = parser.parse_args()

    assets_dir = os.path.expanduser(args.assets_dir)
    filenames = sorted(f for f in os.listdir(assets_dir) if f.lower().endswith(".png"))
    print(f"Found {len(filenames)} local images in {assets_dir}")

    s3 = None
    if not args.dry_run:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("AWS_REGION", "us-east-2"),
        )

    uploaded = skipped_exists = 0
    for filename in filenames:
        local_path = os.path.join(assets_dir, filename)
        s3_key = S3_PREFIX + filename

        if args.dry_run:
            print(f"  [dry-run] would upload {local_path} -> s3://{S3_BUCKET_NAME}/{s3_key}")
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
            s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=fh, ContentType="image/png")
        uploaded += 1

    print(f"\nUploaded: {uploaded}, already present: {skipped_exists}, total: {len(filenames)}")


if __name__ == "__main__":
    main()
