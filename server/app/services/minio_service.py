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
    _public_client: Optional[Minio] = None

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
    def get_public_client(cls) -> Minio:
        """用于「签对外下载直链」的客户端。

        预签名 URL 的签名跟 Host 绑定：在容器里用 MINIO_ENDPOINT=minio:9000 签出来
        的链接，浏览器既解析不了 minio 这个主机名，签名也跟 localhost 对不上，图片/
        文件全都加载不出来。所以签名要单独用对外地址（MINIO_PUBLIC_ENDPOINT）。
        未配置时退回内部客户端，保持旧行为。

        注意：minio-py 在签名前会调 _get_region()，而它会向「客户端自己的 endpoint」
        发一个 GetBucketLocation 请求。对外地址在容器内通常不可达，所以这里必须显式
        传入 region —— 有了 region，SDK 就直接返回、不再发那次请求（否则签名会因连不
        上 localhost 而失败）。region 用内部客户端（能连上 minio:9000）查一次即可。
        该客户端只用于签名、不做实际读写，因此不需要 ensure bucket。
        """
        public_endpoint = (settings.MINIO_PUBLIC_ENDPOINT or "").strip()
        if not public_endpoint:
            return cls.get_client()
        if cls._public_client is None:
            secure = settings.MINIO_SECURE
            if public_endpoint.startswith("https://"):
                secure = True
            elif public_endpoint.startswith("http://"):
                secure = False
            endpoint = public_endpoint.replace("http://", "").replace("https://", "").rstrip("/")
            try:
                region = cls.get_client()._get_region(settings.MINIO_BUCKET_NAME)
            except Exception as e:
                logger.warning("MinIO region lookup failed, signing may need network: %s", e)
                region = None
            cls._public_client = Minio(
                endpoint=endpoint,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=secure,
                region=region
            )
        return cls._public_client

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
        """Generates temporary pre-signed S3 download URL for client browser access.

        Uses the public endpoint for signing (see ``get_public_client``), because the
        signature is bound to the Host header and the container hostname is not
        resolvable from the browser.
        """
        try:
            client = cls.get_public_client()
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
