"""
S3 Object Storage service for certificate uploads.
"""
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

_s3_client = None


def get_s3_client():
    """Get or create singleton S3 client."""
    global _s3_client
    if _s3_client is None:
        endpoint = os.getenv("S3_ENDPOINT")
        access_key = os.getenv("S3_ACCESS_KEY_ID")
        secret_key = os.getenv("S3_SECRET_ACCESS_KEY")

        if not all([endpoint, access_key, secret_key]):
            raise ValueError("S3_ENDPOINT, S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY must be set.")

        _s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
    return _s3_client


def upload_certificate_pdf(key: str, pdf_bytes: bytes) -> str:
    """Upload certificate PDF bytes to S3 bucket and return presigned download URL.

    Args:
        key: Target object key (e.g. certificates/cert_123.pdf)
        pdf_bytes: PDF content as bytes

    Returns:
        Presigned download URL valid for 7 days
    """
    client = get_s3_client()
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise ValueError("S3_BUCKET must be set in .env")

    # Upload to S3
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    # Generate presigned download URL valid for 7 days
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600 * 24 * 7,
    )
    return url
