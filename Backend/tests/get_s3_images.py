import boto3
import botocore

S3_BUCKET_NAME = "smartgreenhouse-2025"
S3_REGION = "eu-north-1"

s3_handler = boto3.client("s3", region_name=S3_REGION)

def download_file(bucket_name: str, object_key: str, download_path: str) -> None:
        try:
            s3_handler.download_file(bucket_name, object_key, download_path)
            print(f"File {object_key} downloaded to {download_path}.")
        except botocore.exceptions.NoCredentialsError:
            print("❌ AWS credentials not found. Run 'aws configure'.")
        except botocore.exceptions.PartialCredentialsError:
            print("❌ Incomplete AWS credentials.")
        except botocore.exceptions.ClientError as e:
            print(f"❌ AWS Client Error: {e}")
        except FileNotFoundError:
            print("❌ Local file not found. Check FILE_PATH.")
        except Exception as e:
            print(f"❌ Error downloading file: {e}")
            
def download_last_x_images(bucket_name: str, prefix: str, x: int) -> None:
    try:
        if prefix != None:
            response = s3_handler.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        else:
            response = s3_handler.list_objects_v2(Bucket=bucket_name)

        if 'Contents' in response:
            objects = sorted(response['Contents'], key=lambda obj: obj['LastModified'], reverse=True)[:x]
            for obj in objects:
                object_key = obj['Key']
                download_path = f"downloaded_{object_key.split('/')[-1]}"
                download_file(bucket_name, object_key, download_path)
        else:
            print("❌ No objects found with the specified prefix.")
    except botocore.exceptions.NoCredentialsError:
        print("❌ AWS credentials not found. Run 'aws configure'.")
    except botocore.exceptions.PartialCredentialsError:
        print("❌ Incomplete AWS credentials.")
    except botocore.exceptions.ClientError as e:
        print(f"❌ AWS Client Error: {e}")
    except Exception as e:
        print(f"❌ Error downloading last {x} images: {e}")


if __name__ == "__main__":
    download_last_x_images(S3_BUCKET_NAME, None, 4)