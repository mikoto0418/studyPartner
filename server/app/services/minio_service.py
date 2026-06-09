import io
import logging
from datetime import timedelta
from typing import BinaryIO, Optional
from minio import Minio
from minio.error import S3Error
from app.config import settings

logger = logging.getLogger(__name__)

class MinioService:
    _client: Optional[Minio] = None

    @classmethod
    def get_client(cls) -> Minio:
        if cls._client is None:
            # Parse endpoint (strip protocol prefix if present)
            endpoint = settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
            cls._client = Minio(
                endpoint=endpoint,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            # Ensure bucket exists
            cls._ensure_bucket_exists(settings.MINIO_BUCKET_NAME)
        return cls._client

    @classmethod
    def _ensure_bucket_exists(cls, bucket_name: str):
        try:
            client = cls._client
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                logger.info(f"Successfully created MinIO bucket: {bucket_name}")
        except S3Error as e:
            logger.error(f"S3 Error ensuring bucket exists: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to ensure MinIO bucket exists: {e}", exc_info=True)

    @classmethod
    def upload_file(
        cls,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream"
    ) -> str:
        """Uploads file to MinIO and returns object name path"""
        try:
            client = cls.get_client()
            client.put_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type
            )
            logger.info(f"Successfully uploaded object {object_name} to MinIO.")
            return object_name
        except Exception as e:
            logger.error(f"MinIO upload_file failed for {object_name}: {e}", exc_info=True)
            raise e

    @classmethod
    def download_file(cls, object_name: str) -> bytes:
        """Downloads file contents as raw bytes from MinIO"""
        try:
            client = cls.get_client()
            response = client.get_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name
            )
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as e:
            logger.error(f"MinIO download_file failed for {object_name}: {e}", exc_info=True)
            raise e

    @classmethod
    def get_download_url(cls, object_name: str, expires_seconds: int = 3600) -> str:
        """Generates temporary pre-signed S3 download URL for client browser access"""
        try:
            client = cls.get_client()
            url = client.presigned_get_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds)
            )
            return url
        except Exception as e:
            logger.error(f"MinIO get_download_url failed for {object_name}: {e}", exc_info=True)
            raise e

    @classmethod
    def delete_file(cls, object_name: str) -> bool:
        """Removes file object from MinIO"""
        try:
            client = cls.get_client()
            client.remove_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name
            )
            logger.info(f"Successfully deleted object {object_name} from MinIO.")
            return True
        except Exception as e:
            logger.error(f"MinIO delete_file failed for {object_name}: {e}", exc_info=True)
            return False
