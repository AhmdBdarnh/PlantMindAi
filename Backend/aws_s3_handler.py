import boto3
import botocore
import io
from utils.utils import _CUSTOM_PRINT_FUNC

class S3Handler:
    def __init__(self, bucket_name: str, region_name: str = 'us-east-1'):
        self.__s3_client = boto3.client('s3')
        self.__bucket_name = bucket_name
        self.__s3_region = region_name        

    def upload_file(self, file_path: str, object_name: str) -> None:
        try:
            with open(file_path, 'rb') as file:            
                self.__s3_client.upload_fileobj(io.BytesIO(file.read()), self.__bucket_name, object_name)
                _CUSTOM_PRINT_FUNC(f"File {file_path} uploaded to {self.__bucket_name}/{object_name}.")
        except botocore.exceptions.NoCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ AWS credentials not found. Run 'aws configure'.")
        except botocore.exceptions.PartialCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ Incomplete AWS credentials.")
        except botocore.exceptions.ClientError as e:
            _CUSTOM_PRINT_FUNC(f"❌ AWS Client Error: {e}")
        except FileNotFoundError:
            _CUSTOM_PRINT_FUNC("❌ Local file not found. Check FILE_PATH.")

    def get_s3_url(self, object_key: str) -> str:
        try:
            return f"https://{self.__bucket_name}.s3.{self.__s3_region}.amazonaws.com/{object_key}"
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"❌ Error generating S3 URL: {e}")
            return None
        
    def download_file(self, object_key: str, download_path: str) -> None:
        try:
            self.__s3_client.download_file(self.__bucket_name, object_key, download_path)
            _CUSTOM_PRINT_FUNC(f"File {object_key} downloaded to {download_path}.")
        except botocore.exceptions.NoCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ AWS credentials not found. Run 'aws configure'.")
        except botocore.exceptions.PartialCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ Incomplete AWS credentials.")
        except botocore.exceptions.ClientError as e:
            _CUSTOM_PRINT_FUNC(f"❌ AWS Client Error: {e}")
        except FileNotFoundError:
            _CUSTOM_PRINT_FUNC("❌ Local file not found. Check FILE_PATH.")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"❌ Error downloading file: {e}")

    def download_last_x_images(self, prefix: str, x: int) -> None:
        try:
            response = self.__s3_client.list_objects_v2(Bucket=self.__bucket_name, Prefix=prefix)
            if 'Contents' in response:
                objects = sorted(response['Contents'], key=lambda obj: obj['LastModified'], reverse=True)[:x]
                for obj in objects:
                    object_key = obj['Key']
                    download_path = f"downloaded_{object_key.split('/')[-1]}"
                    self.download_file(object_key, download_path)
            else:
                _CUSTOM_PRINT_FUNC("❌ No objects found with the specified prefix.")
        except botocore.exceptions.NoCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ AWS credentials not found. Run 'aws configure'.")
        except botocore.exceptions.PartialCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ Incomplete AWS credentials.")
        except botocore.exceptions.ClientError as e:
            _CUSTOM_PRINT_FUNC(f"❌ AWS Client Error: {e}")
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"❌ Error downloading last {x} images: {e}")
    
    def get_num_of_files(self, prefix: str = None) -> int:
        try:
            if prefix is not None:
                response = self.__s3_client.list_objects_v2(Bucket=self.__bucket_name, Prefix=prefix)
            else:
                response = self.__s3_client.list_objects_v2(Bucket=self.__bucket_name)

            if 'Contents' in response:
                return len(response['Contents'])
            else:
                _CUSTOM_PRINT_FUNC("❌ No objects found.")
                return 0
        except botocore.exceptions.NoCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ AWS credentials not found. Run 'aws configure'.")
            return 0
        except botocore.exceptions.PartialCredentialsError:
            _CUSTOM_PRINT_FUNC("❌ Incomplete AWS credentials.")
            return 0
        except botocore.exceptions.ClientError as e:
            _CUSTOM_PRINT_FUNC(f"❌ AWS Client Error: {e}")
            return 0
        except Exception as e:
            _CUSTOM_PRINT_FUNC(f"❌ Error getting number of files: {e}")
            return 0