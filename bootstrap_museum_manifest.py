"""
One-off script: generate museum-manifest.json from all existing S3 images.
Run once: python bootstrap_museum_manifest.py
"""
import boto3
import json
from urllib.parse import quote

s3 = boto3.client("s3")
bucket = "triviabotwebsite"
prefix = "generated-images/"

all_items = []
kwargs = {"Bucket": bucket, "Prefix": prefix}
while True:
    response = s3.list_objects_v2(**kwargs)
    all_items.extend(response.get("Contents", []))
    if response.get("IsTruncated"):
        kwargs["ContinuationToken"] = response["NextContinuationToken"]
    else:
        break

images = []
for item in all_items:
    if item["Key"].endswith((".png", ".jpg", ".jpeg", ".gif")):
        name = item["Key"].split("/")[-1].rsplit(".", 1)[0]
        images.append({
            "url": f"https://triviabotwebsite.s3.amazonaws.com/{quote(item['Key'], safe='/')}",
            "name": name,
            "last_modified": item["LastModified"].isoformat(),
        })

images.sort(key=lambda x: x["last_modified"], reverse=True)
print(f"Found {len(images)} images. Uploading manifest...")

s3.put_object(
    Bucket=bucket,
    Key="static/museum-manifest.json",
    Body=json.dumps(images),
    ContentType="application/json",
    ACL="public-read",
)
print("Done. museum-manifest.json is live.")
