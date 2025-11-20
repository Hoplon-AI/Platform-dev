from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
from preprocessing import standardize_columns

app = FastAPI()

# Configure CORS to allow requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],  # React default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload CSV file, standardize columns, and return the processed data.
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    try:
        # Read file contents
        contents = await file.read()

        # Convert bytes to pandas DataFrame
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))

        # Store original column names
        original_columns = df.columns.tolist()

        # Standardize column names
        df_standardized = standardize_columns(df)

        # Get standardized column names
        standardized_columns = df_standardized.columns.tolist()

        # Replace NaN values with None for JSON serialization
        df_standardized = df_standardized.where(pd.notna(df_standardized), None)

        # Convert DataFrame to dictionary for JSON response
        # Using 'records' orientation to get list of row dictionaries
        data = df_standardized.to_dict('records')

        # Prepare column mapping to show what changed
        column_mapping = {
            original: standardized
            for original, standardized in zip(original_columns, standardized_columns)
            if original != standardized
        }

        return {
            "success": True,
            "message": f"Successfully processed {len(df)} rows",
            "columns": standardized_columns,
            "data": data,
            "column_mapping": column_mapping,
            "row_count": len(df),
            "original_filename": file.filename
        }

    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="The uploaded CSV file is empty")
    except pd.errors.ParserError:
        raise HTTPException(status_code=400, detail="Failed to parse CSV file. Please check the file format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "API is running"}