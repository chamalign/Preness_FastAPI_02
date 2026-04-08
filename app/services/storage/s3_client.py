"""
S3 に音声 bytes をアップロードし、URL を返す.
bucket/region 未設定時は None を返す.
"""

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def upload_audio_bytes(
    data: bytes,
    object_key: str,
    content_type: str = "audio/wav",
) -> str:
    """
    bytes を S3 にアップロードし、オブジェクトの URL を返す.
    失敗時は ValueError を送出する.
    """
    settings = get_settings()
    if not settings.s3_bucket or not settings.s3_region:
        logger.debug("S3 未設定 (S3_BUCKET / S3_REGION)")
        raise ValueError("S3 設定が不足しています: S3_BUCKET / S3_REGION を設定してください")
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        logger.debug("AWS 認証情報未設定")
        raise ValueError(
            "AWS 認証情報が不足しています: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY を設定してください"
        )

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        logger.warning("boto3 がインストールされていません")
        raise ValueError("boto3 が未導入です: boto3 と botocore をインストールしてください")

    client = boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        url = f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{object_key}"
        return url
    except ClientError as e:
        logger.error("S3 アップロード失敗: %s", e)
        raise ValueError(
            f"S3 アップロード失敗: bucket={settings.s3_bucket}, key={object_key}, error={e}"
        )
