import io
import os
from pathlib import Path

import boto3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "platform-bronze")
S3_KEY = os.getenv("S3_KEY", "test.csv")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "platform_dev")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name=S3_REGION,
    )


def download_csv_from_s3(bucket: str, key: str) -> pd.DataFrame:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    return pd.read_csv(io.BytesIO(body))


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def ensure_test_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.s3_test_ingest (
                id SERIAL PRIMARY KEY,
                source_key TEXT NOT NULL,
                row_data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
    conn.commit()


def insert_dataframe(conn, df: pd.DataFrame, source_key: str):
    records = [(source_key, row.to_json(date_format="iso")) for _, row in df.iterrows()]

    if not records:
        print("No rows to insert.")
        return

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO public.s3_test_ingest (source_key, row_data)
            VALUES %s
            """,
            records,
            template="(%s, %s::jsonb)",
        )
    conn.commit()
    print(f"Inserted {len(records)} rows into public.s3_test_ingest")


def main():
    print(f"Downloading s3://{S3_BUCKET}/{S3_KEY}")
    df = download_csv_from_s3(S3_BUCKET, S3_KEY)
    print("CSV loaded.")
    print(df.head())

    conn = get_db_connection()
    try:
        ensure_test_table(conn)
        insert_dataframe(conn, df, S3_KEY)
    finally:
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()