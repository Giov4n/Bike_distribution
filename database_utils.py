import pandas as pd
import pymongo
import gridfs
import io
import re
import datetime
import pandas as pd
import zlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Try to import streamlit for secrets, fall back to environment variables
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    import os


def get_mongo_config():
    """
    Get MongoDB configuration from streamlit secrets or environment variables.
    Priority: 1. Streamlit secrets, 2. Environment variables
    """
    if HAS_STREAMLIT:
        try:
            return {
                'uri': st.secrets["mongo_uri"],
                'db_name': st.secrets.get("db_name", "my_database"),
                'default_user_id': st.secrets.get("default_user_id", "analyst_01")
            }
        except Exception:
            pass
    
    # Fallback to environment variables
    return {
        'uri': os.getenv('MONGO_URI', 'mongodb://localhost:27017/'),
        'db_name': os.getenv('MONGO_DB_NAME', 'my_database'),
        'default_user_id': os.getenv('MONGO_USER_ID', 'analyst_01')
    }


class SecureGridFSHandler:
    def __init__(self, connection_string=None, db_name=None):
        """
        Initialize handler with MongoDB connection.
        
        Args:
            connection_string: MongoDB URI (if None, reads from secrets.toml or env vars)
            db_name: Database name (if None, reads from secrets.toml or env vars)
        """
        # Get config from secrets if not provided
        if connection_string is None or db_name is None:
            config = get_mongo_config()
            connection_string = connection_string or config['uri']
            db_name = db_name or config['db_name']
        
        self.client = pymongo.MongoClient(
            connection_string,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000
        )
        self.db = self.client[db_name]
        self.fs = gridfs.GridFS(self.db)
        self._setup_indexes()
        self._sanitize_regex = re.compile(r'[^a-zA-Z0-9_\-]')
    
    def _setup_indexes(self):
        files_col = self.db['fs.files']
        try:
            files_col.create_index(
                [("metadata.owner_id", 1), ("filename", 1)], 
                name="owner_filename_idx",
                background=True
            )
            files_col.create_index(
                [("metadata.owner_id", 1)], 
                name="owner_only_idx",
                background=True
            )
            files_col.create_index(
                [("metadata.owner_id", 1), ("metadata.type", 1)],
                name="owner_type_idx",
                background=True
            )
        except pymongo.errors.OperationFailure:
            pass
    
    def _sanitize_key(self, key):
        return self._sanitize_regex.sub('', key)
    
    def save_dataframe(self, user_id, df_name, df):
        """Saves DataFrame to GridFS with compression."""
        safe_name = self._sanitize_key(df_name)
        buffer = io.BytesIO()
        
        df.to_parquet(
            buffer, 
            engine='pyarrow', 
            index=False,
            compression='snappy'
        )
        buffer.seek(0)
        
        self.db['fs.files'].find_one_and_delete({
            "filename": safe_name, 
            "metadata.owner_id": user_id
        })
        
        col_count = len(df.columns)
        
        self.fs.put(
            buffer, 
            filename=safe_name, 
            metadata={
                "owner_id": user_id,
                "type": "dataframe",
                "row_count": len(df),
                "col_count": col_count,
                "created_at": datetime.datetime.utcnow()
            }
        )
        print(f"✅ Saved DataFrame '{df_name}': {len(df):,} rows, {col_count} columns")
    
    def load_dataframe(self, user_id, df_name):
        """Loads DataFrame from GridFS."""
        safe_name = self._sanitize_key(df_name)
        file_doc = self.fs.find_one({
            "filename": safe_name, 
            "metadata.owner_id": user_id
        })
        
        if not file_doc:
            return None
        
        return pd.read_parquet(io.BytesIO(file_doc.read()))
    
    def list_dataframes(self, user_id):
        """Lists all DataFrames for a user."""
        cursor = self.db['fs.files'].find(
            {"metadata.owner_id": user_id, "metadata.type": "dataframe"}, 
            {
                "filename": 1, 
                "metadata.row_count": 1,
                "metadata.col_count": 1,
                "metadata.created_at": 1,
                "length": 1,
                "_id": 0
            }
        ).sort("metadata.created_at", -1)
        return list(cursor)
    
    def save_map_html(self, user_id, map_name, html_string):
        """Saves HTML with optimal compression and chunking."""
        safe_name = self._sanitize_key(map_name) + ".html"
        
        self.db['fs.files'].find_one_and_delete({
            "filename": safe_name,
            "metadata.owner_id": user_id
        })
        
        compressed = zlib.compress(html_string.encode('utf-8'), level=6)
        
        self.fs.put(
            compressed,
            filename=safe_name,
            metadata={
                "owner_id": user_id,
                "type": "map_html",
                "compressed": True,
                "original_size": len(html_string),
                "compressed_size": len(compressed),
                "created_at": datetime.datetime.utcnow()
            },
            chunk_size=261120
        )
        
        compression_ratio = (1 - len(compressed) / len(html_string)) * 100
        print(f"✅ Saved HTML '{map_name}': {len(html_string):,} bytes → {len(compressed):,} bytes ({compression_ratio:.1f}% compression)")
    
    def load_map_html(self, user_id, map_name):
        """Fast retrieval with streaming decompression."""
        safe_name = self._sanitize_key(map_name) + ".html"
        
        file_doc = self.fs.find_one({
            "filename": safe_name,
            "metadata.owner_id": user_id
        })
        
        if not file_doc:
            return None
        
        content = file_doc.read()
        
        if file_doc.metadata and file_doc.metadata.get("compressed"):
            return zlib.decompress(content).decode('utf-8')
        else:
            return content.decode('utf-8')
    
    def list_maps(self, user_id):
        """List all maps with size information."""
        cursor = self.db['fs.files'].find(
            {"metadata.owner_id": user_id, "metadata.type": "map_html"},
            {
                "filename": 1,
                "metadata.original_size": 1,
                "metadata.compressed_size": 1,
                "metadata.created_at": 1,
                "_id": 0
            }
        ).sort("metadata.created_at", -1)
        
        return [
            {
                "name": doc["filename"].replace(".html", ""),
                "size_mb": doc.get("metadata", {}).get("original_size", 0) / 1024 / 1024,
                "compressed_mb": doc.get("metadata", {}).get("compressed_size", 0) / 1024 / 1024,
                "created": doc.get("metadata", {}).get("created_at")
            }
            for doc in cursor
        ]
    
    def save_csv_from_file(self, user_id, csv_file_path, dataset_name=None):
        """Loads CSV from local file and saves to GridFS as DataFrame."""
        csv_path = Path(csv_file_path)
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        
        if dataset_name is None:
            dataset_name = csv_path.stem
        
        print(f"📂 Reading CSV: {csv_path.name}...")
        df = pd.read_csv(csv_path, low_memory=False, engine='c')
        
        self.save_dataframe(user_id, dataset_name, df)
        return df
    
    def save_html_from_file(self, user_id, html_file_path, map_name=None):
        """Loads HTML from local file and saves to GridFS."""
        html_path = Path(html_file_path)
        
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_file_path}")
        
        if map_name is None:
            map_name = html_path.stem
        
        print(f"📂 Reading HTML: {html_path.name}...")
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        self.save_map_html(user_id, map_name, html_content)
        return html_content
    
    def save_multiple_csvs(self, user_id, folder_path, pattern="*.csv"):
        """Batch upload multiple CSV files from a folder."""
        folder = Path(folder_path)
        
        if not folder.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        csv_files = list(folder.glob(pattern))
        
        if not csv_files:
            print(f"⚠️ No CSV files found in {folder_path}")
            return []
        
        print(f"📦 Found {len(csv_files)} CSV files. Starting batch upload...")
        
        results = []
        for i, csv_file in enumerate(csv_files, 1):
            try:
                print(f"\n[{i}/{len(csv_files)}] Processing: {csv_file.name}")
                df = self.save_csv_from_file(user_id, csv_file)
                results.append({
                    "file": csv_file.name,
                    "status": "success",
                    "rows": len(df),
                    "columns": len(df.columns)
                })
            except Exception as e:
                print(f"❌ Error processing {csv_file.name}: {e}")
                results.append({
                    "file": csv_file.name,
                    "status": "failed",
                    "error": str(e)
                })
        
        print(f"\n✅ Batch upload complete: {sum(1 for r in results if r['status'] == 'success')}/{len(results)} successful")
        return results
    
    def save_multiple_htmls(self, user_id, folder_path, pattern="*.html"):
        """Batch upload multiple HTML files from a folder."""
        folder = Path(folder_path)
        
        if not folder.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        html_files = list(folder.glob(pattern))
        
        if not html_files:
            print(f"⚠️ No HTML files found in {folder_path}")
            return []
        
        print(f"📦 Found {len(html_files)} HTML files. Starting batch upload...")
        
        results = []
        for i, html_file in enumerate(html_files, 1):
            try:
                print(f"\n[{i}/{len(html_files)}] Processing: {html_file.name}")
                self.save_html_from_file(user_id, html_file)
                results.append({
                    "file": html_file.name,
                    "status": "success"
                })
            except Exception as e:
                print(f"❌ Error processing {html_file.name}: {e}")
                results.append({
                    "file": html_file.name,
                    "status": "failed",
                    "error": str(e)
                })
        
        print(f"\n✅ Batch upload complete: {sum(1 for r in results if r['status'] == 'success')}/{len(results)} successful")
        return results
    
    def export_dataframe_to_csv(self, user_id, dataset_name, output_path):
        """Export DataFrame from GridFS back to CSV file."""
        df = self.load_dataframe(user_id, dataset_name)
        
        if df is None:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output, index=False)
        print(f"✅ Exported to: {output}")
        return df
    
    def export_html_to_file(self, user_id, map_name, output_path):
        """Export HTML from GridFS back to file."""
        html_content = self.load_map_html(user_id, map_name)
        
        if html_content is None:
            raise ValueError(f"Map '{map_name}' not found")
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Exported to: {output}")
        return html_content

    def load_image(self, user_id, image_name):
        """
        Retrieves an image from GridFS.
    
        Args:
            user_id: User identifier
            image_name: Name of the image file
    
        Returns:
            bytes: Image data, or None if not found
        """
        file_doc = self.fs.find_one({
            "filename": image_name,
            "metadata.owner_id": user_id
        })
    
        if not file_doc:
            return None
    
        return file_doc.read()

    def save_image_to_file(self, user_id, image_name, output_path):
        """
        Export image from GridFS back to file.
    
        Args:
            user_id: User identifier
            image_name: Name of the image in MongoDB
            output_path: Where to save the image
    
        Returns:
            bool: Success status
        """
        image_data = self.load_image(user_id, image_name)
    
        if image_data is None:
            print(f"❌ Image '{image_name}' not found")
            return False
    
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
    
        with open(output, 'wb') as f:
            f.write(image_data)
    
        print(f"✅ Exported image to: {output}")
        return True
    
    def delete_dataframe(self, user_id, df_name):
        """Deletes a DataFrame from GridFS."""
        safe_name = self._sanitize_key(df_name)
        result = self.db['fs.files'].find_one_and_delete({
            "filename": safe_name,
            "metadata.owner_id": user_id,
            "metadata.type": "dataframe"
        })
        if result:
            print(f"✅ Deleted DataFrame: {df_name}")
        return result is not None
    
    def delete_map_html(self, user_id, map_name):
        """Deletes a map HTML from GridFS."""
        safe_name = self._sanitize_key(map_name) + ".html"
        result = self.db['fs.files'].find_one_and_delete({
            "filename": safe_name,
            "metadata.owner_id": user_id,
            "metadata.type": "map_html"
        })
        if result:
            print(f"✅ Deleted HTML map: {map_name}")
        return result is not None
    
    def get_storage_stats(self, user_id):
        """Get storage statistics for a user."""
        pipeline = [
            {"$match": {"metadata.owner_id": user_id}},
            {"$group": {
                "_id": "$metadata.type",
                "count": {"$sum": 1},
                "total_size": {"$sum": "$length"}
            }}
        ]
        
        stats = list(self.db['fs.files'].aggregate(pipeline))
        
        result = {
            "total_files": 0,
            "total_size_mb": 0,
            "by_type": {}
        }
        
        for stat in stats:
            file_type = stat["_id"] or "unknown"
            count = stat["count"]
            size_mb = stat["total_size"] / 1024 / 1024
            
            result["total_files"] += count
            result["total_size_mb"] += size_mb
            result["by_type"][file_type] = {
                "count": count,
                "size_mb": round(size_mb, 2)
            }
        
        result["total_size_mb"] = round(result["total_size_mb"], 2)
        return result
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()

#####################################################################################################

class SecureBulkUploader:
    def __init__(self, connection_string=None, db_name=None):
        """
        Initialize uploader with MongoDB connection.
        
        Args:
            connection_string: MongoDB URI (if None, reads from secrets.toml or env vars)
            db_name: Database name (if None, reads from secrets.toml or env vars)
        """
        # Get config from secrets if not provided
        if connection_string is None or db_name is None:
            config = get_mongo_config()
            connection_string = connection_string or config['uri']
            db_name = db_name or config['db_name']
        
        self.client = pymongo.MongoClient(
            connection_string,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            connectTimeoutMS=10000,
            serverSelectionTimeoutMS=10000
        )
        self.db = self.client[db_name]
        self.fs = gridfs.GridFS(self.db)
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Ensures the database is optimized for the dashboard later."""
        files_col = self.db['fs.files']
        try:
            files_col.create_index(
                [("metadata.owner_id", 1), ("filename", 1)],
                name="owner_filename_idx",
                background=True
            )
            files_col.create_index(
                [("metadata.owner_id", 1)],
                name="owner_only_idx",
                background=True
            )
            files_col.create_index(
                [("metadata.owner_id", 1), ("metadata.type", 1)],
                name="owner_type_idx",
                background=True
            )
        except pymongo.errors.OperationFailure:
            pass
    
    def _process_csv_file(self, target_path: Path, filename: str, user_id: str, compress: bool = True):
        """
        Process and upload a CSV file as Parquet.
        
        Args:
            target_path: Path object to the CSV file
            filename: Name to use in MongoDB
            user_id: User identifier
            compress: Whether to compress the parquet data
        
        Returns:
            dict: Result status
        """
        try:
            # Read CSV with optimizations
            df = pd.read_csv(
                target_path,
                low_memory=False,
                engine='c'
            )
            
            # Convert to Parquet buffer
            buffer = io.BytesIO()
            df.to_parquet(
                buffer,
                engine='pyarrow',
                index=False,
                compression='snappy'
            )
            buffer.seek(0)
            
            # Optional: Additional compression for large files
            data = buffer.getvalue()
            if compress and len(data) > 1024 * 1024:  # > 1MB
                data = zlib.compress(data, level=6)
                compressed = True
            else:
                compressed = False
            
            # Atomic delete of existing version
            self.db['fs.files'].find_one_and_delete({
                "filename": filename,
                "metadata.owner_id": user_id
            })
            
            # Push to GridFS with metadata
            self.fs.put(
                data,
                filename=filename,
                metadata={
                    "owner_id": user_id,
                    "type": "dataframe",
                    "row_count": len(df),
                    "col_count": len(df.columns),
                    "upload_type": "bulk_script",
                    "compressed": compressed,
                    "original_size": len(buffer.getvalue()) if compressed else None,
                    "created_at": datetime.datetime.utcnow()
                },
                chunk_size=261120
            )
            
            return {
                "filename": filename,
                "file_type": "csv",
                "status": "success",
                "rows": len(df),
                "columns": len(df.columns),
                "size_mb": len(data) / 1024 / 1024
            }
            
        except Exception as e:
            return {
                "filename": filename,
                "file_type": "csv",
                "status": "failed",
                "error": str(e)
            }

    def _process_image_file(self, target_path: Path, filename: str, user_id: str):
        """
        Process and upload an image file.
    
        Args:
            target_path: Path object to the image file
            filename: Name to use in MongoDB
            user_id: User identifier
    
        Returns:
            dict: Result status
        """
        try:
            # Read image file as binary
            with open(target_path, 'rb') as f:
                image_data = f.read()
        
            # Get image metadata
            file_size = len(image_data)
            file_extension = target_path.suffix.lower()
        
            # Atomic delete of existing version
            self.db['fs.files'].find_one_and_delete({
                "filename": filename,
                "metadata.owner_id": user_id
            })
        
            # Push to GridFS with metadata
            self.fs.put(
                image_data,
                filename=filename,
                metadata={
                    "owner_id": user_id,
                    "type": "image",
                    "image_format": file_extension.replace('.', ''),
                    "file_size": file_size,
                    "upload_type": "bulk_script",
                    "created_at": datetime.datetime.utcnow()
                },
                chunk_size=261120
            )
        
            return {
                "filename": filename,
                "file_type": "image",
                "status": "success",
                "size_mb": file_size / 1024 / 1024,
                "format": file_extension
            }
        
        except Exception as e:
            return {
                "filename": filename,
                "file_type": "image",
                "status": "failed",
                "error": str(e)
            }
        
    def _process_html_file(self, target_path: Path, filename: str, user_id: str):
        """
        Process and upload an HTML file with compression.
        
        Args:
            target_path: Path object to the HTML file
            filename: Name to use in MongoDB
            user_id: User identifier
        
        Returns:
            dict: Result status
        """
        try:
            # Read HTML file
            with open(target_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Compress HTML (typically 70-90% compression)
            compressed = zlib.compress(html_content.encode('utf-8'), level=6)
            
            # Atomic delete of existing version
            safe_name = filename if filename.endswith('.html') else f"{filename}.html"
            self.db['fs.files'].find_one_and_delete({
                "filename": safe_name,
                "metadata.owner_id": user_id
            })
            
            # Push to GridFS with metadata
            self.fs.put(
                compressed,
                filename=safe_name,
                metadata={
                    "owner_id": user_id,
                    "type": "map_html",
                    "compressed": True,
                    "original_size": len(html_content),
                    "compressed_size": len(compressed),
                    "upload_type": "bulk_script",
                    "created_at": datetime.datetime.utcnow()
                },
                chunk_size=261120
            )
            
            compression_ratio = (1 - len(compressed) / len(html_content)) * 100
            
            return {
                "filename": safe_name,
                "file_type": "html",
                "status": "success",
                "original_size_mb": len(html_content) / 1024 / 1024,
                "compressed_size_mb": len(compressed) / 1024 / 1024,
                "compression_ratio": compression_ratio
            }
            
        except Exception as e:
            return {
                "filename": filename,
                "file_type": "html",
                "status": "failed",
                "error": str(e)
            }
    
    def _process_single_file(self, target_path: Path, filename: str, user_id: str, compress: bool = True):
        """
        Process and upload a single file (CSV, HTML, or Image).
        Automatically detects file type by extension.
    
        Args:
            target_path: Path object to the file
            filename: Name to use in MongoDB
            user_id: User identifier
            compress: Whether to compress the data
    
        Returns:
            dict: Result status
        """
        file_extension = target_path.suffix.lower()
    
        # CSV files
        if file_extension == '.csv':
            return self._process_csv_file(target_path, filename, user_id, compress)
    
        # HTML files
        elif file_extension in ['.html', '.htm']:
            return self._process_html_file(target_path, filename, user_id)
    
        # Image files
        elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico']:
            return self._process_image_file(target_path, filename, user_id)
    
        else:
            return {
                "filename": filename,
                "file_type": file_extension,
                "status": "failed",
                "error": f"Unsupported file type: {file_extension}. Supported: .csv, .html, .jpg, .png, .gif, .bmp, .svg, .webp"
            }
    
    def upload_files(self, base_folder: str, file_list: list, user_id: str, 
                     parallel: bool = True, max_workers: int = 4, compress: bool = True):
        """
        Safely finds and uploads specific files (CSV or HTML) from a local folder.
        
        Args:
            base_folder: Base directory containing files
            file_list: List of filenames to upload (can be .csv or .html files)
            user_id: User identifier
            parallel: Whether to use parallel uploads (faster for multiple files)
            max_workers: Number of parallel upload threads (default: 4)
            compress: Whether to compress large files (default: True)
        
        Returns:
            dict: Summary of upload results
        """
        # Pathlib Gatekeeper: Define and resolve the safe folder
        safe_base = Path(base_folder).resolve()
        
        if not safe_base.is_dir():
            raise ValueError(f"The path {base_folder} is not a valid directory.")
        
        print(f"🚀 Starting bulk upload from: {safe_base}")
        print(f"📦 Files to process: {len(file_list)}")
        print(f"⚡ Parallel mode: {'ON' if parallel else 'OFF'}")
        print(f"🗜️  Compression: {'ON' if compress else 'OFF'}")
        print("="*60)
        
        # Validate all files first
        valid_files = []
        for filename in file_list:
            target_path = (safe_base / filename).resolve()
            
            # Security Checks
            if not target_path.exists():
                print(f"⚠️  Skipping: {filename} (File not found)")
                continue
            
            if not target_path.is_relative_to(safe_base):
                print(f"🚫 Security Block: {filename} is outside the safe directory!")
                continue
            
            if target_path.is_symlink():
                print(f"🚫 Security Block: {filename} is a symbolic link!")
                continue
            
            # Check file type
            supported_extensions = ['.csv', '.html', '.htm', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico']
            if target_path.suffix.lower() not in supported_extensions:
                print(f"⚠️  Skipping: {filename} (Only .csv .html and image files supported)")
                continue
            
            valid_files.append((target_path, filename))
        
        if not valid_files:
            print("❌ No valid files to upload")
            return {"total": 0, "success": 0, "failed": 0, "results": []}
        
        print(f"✅ Validated {len(valid_files)} files")
        
        # Count file types
        csv_count = sum(1 for p, _ in valid_files if p.suffix.lower() == '.csv')
        html_count = sum(1 for p, _ in valid_files if p.suffix.lower() in ['.html', '.htm'])
        print(f"   📊 CSV files: {csv_count}")
        print(f"   🗺️  HTML files: {html_count}")
        print("="*60)
        
        # Upload files (parallel or sequential)
        results = []
        
        if parallel and len(valid_files) > 1:
            # Parallel upload using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_file = {
                    executor.submit(
                        self._process_single_file,
                        target_path,
                        filename,
                        user_id,
                        compress
                    ): filename
                    for target_path, filename in valid_files
                }
                
                for future in as_completed(future_to_file):
                    filename = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if result["status"] == "success":
                            if result["file_type"] == "csv":
                                print(f"✅ {result['filename']}: {result['rows']:,} rows, "
                                      f"{result['columns']} cols, {result['size_mb']:.2f} MB")
                            elif result["file_type"] == "html":
                                print(f"✅ {result['filename']}: "
                                      f"{result['original_size_mb']:.2f} MB → "
                                      f"{result['compressed_size_mb']:.2f} MB "
                                      f"({result['compression_ratio']:.1f}% compression)")
                        else:
                            print(f"❌ {result['filename']}: {result['error']}")
                    
                    except Exception as e:
                        print(f"❌ {filename}: Unexpected error - {e}")
                        results.append({
                            "filename": filename,
                            "status": "failed",
                            "error": str(e)
                        })
        else:
            # Sequential upload
            for i, (target_path, filename) in enumerate(valid_files, 1):
                print(f"\n[{i}/{len(valid_files)}] Processing: {filename}...")
                result = self._process_single_file(target_path, filename, user_id, compress)
                results.append(result)
                
                if result["status"] == "success":
                    if result["file_type"] == "csv":
                        print(f"✅ {result['filename']}: {result['rows']:,} rows, "
                              f"{result['columns']} cols, {result['size_mb']:.2f} MB")
                    elif result["file_type"] == "html":
                        print(f"✅ {result['filename']}: "
                              f"{result['original_size_mb']:.2f} MB → "
                              f"{result['compressed_size_mb']:.2f} MB "
                              f"({result['compression_ratio']:.1f}% compression)")
                else:
                    print(f"❌ {result['filename']}: {result['error']}")
        
        # Summary
        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count
        
        csv_success = sum(1 for r in results if r["status"] == "success" and r.get("file_type") == "csv")
        html_success = sum(1 for r in results if r["status"] == "success" and r.get("file_type") == "html")
        
        print("\n" + "="*60)
        print("📊 UPLOAD SUMMARY")
        print("="*60)
        print(f"Total files: {len(results)}")
        print(f"✅ Successful: {success_count} ({csv_success} CSV, {html_success} HTML)")
        print(f"❌ Failed: {failed_count}")
        
        if csv_success > 0:
            total_rows = sum(r.get('rows', 0) for r in results 
                           if r['status'] == 'success' and r.get('file_type') == 'csv')
            total_size = sum(r.get('size_mb', 0) for r in results 
                           if r['status'] == 'success' and r.get('file_type') == 'csv')
            print(f"📊 CSV - Total rows: {total_rows:,}, Size: {total_size:.2f} MB")
        
        if html_success > 0:
            total_html_orig = sum(r.get('original_size_mb', 0) for r in results 
                                 if r['status'] == 'success' and r.get('file_type') == 'html')
            total_html_comp = sum(r.get('compressed_size_mb', 0) for r in results 
                                 if r['status'] == 'success' and r.get('file_type') == 'html')
            print(f"🗺️  HTML - Original: {total_html_orig:.2f} MB, Compressed: {total_html_comp:.2f} MB")
        
        return {
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "csv_count": csv_success,
            "html_count": html_success,
            "results": results
        }
    
    def upload_folder(self, base_folder: str, user_id: str, pattern: str = "*.csv",
                     parallel: bool = True, max_workers: int = 4, compress: bool = True):
        """
        Upload all files matching a pattern from a folder.
        
        Args:
            base_folder: Directory to scan
            user_id: User identifier
            pattern: File pattern (default: "*.csv", can use "*.html" or "*.*" for all)
            parallel: Whether to use parallel uploads
            max_workers: Number of parallel threads
            compress: Whether to compress large files
        """
        safe_base = Path(base_folder).resolve()
        
        if not safe_base.is_dir():
            raise ValueError(f"The path {base_folder} is not a valid directory.")
        
        # Find all matching files
        matched_files = list(safe_base.glob(pattern))
        
        if not matched_files:
            print(f"⚠️  No files matching '{pattern}' found in {base_folder}")
            return {"total": 0, "success": 0, "failed": 0, "results": []}
        
        # Extract filenames
        file_list = [f.name for f in matched_files]
        
        # Upload using main method
        return self.upload_files(base_folder, file_list, user_id, parallel, max_workers, compress)
    
    def __del__(self):
        """Proper cleanup"""
        if hasattr(self, 'client'):
            self.client.close()


# --- EXECUTION BLOCK ---
if __name__ == "__main__":
    
    # Initialize using secrets.toml
    uploader = SecureBulkUploader()
    config = get_mongo_config()
    user_id = config['default_user_id']
    
    print("\n" + "="*60)
    print("EXAMPLE 1: Upload Mixed CSV and HTML Files")
    print("="*60)
    
    # Mix of CSV and HTML files
    TARGET_FILES = [
        "january_trips.csv",
        "february_trips.csv",
        "regional_arcs.csv",
        "station_map.html",
        "traffic_heatmap.html",
        "route_visualization.html"
    ]
    
    results = uploader.upload_files(
        base_folder="./data",
        file_list=TARGET_FILES,
        user_id=user_id,
        parallel=True,
        max_workers=4,
        compress=True
    )
    
    print("\n" + "="*60)
    print("EXAMPLE 2: Upload All HTML Files from Folder")
    print("="*60)
    
    results = uploader.upload_folder(
        base_folder="./data/maps",
        user_id=user_id,
        pattern="*.html",  # Only HTML files
        parallel=True
    )
    
    print("\n" + "="*60)
    print("EXAMPLE 3: Upload All Files (CSV and HTML)")
    print("="*60)
    
    # Upload all CSV files
    results_csv = uploader.upload_folder(
        base_folder="./data",
        user_id=user_id,
        pattern="*.csv",
        parallel=True
    )
    
    # Upload all HTML files
    results_html = uploader.upload_folder(
        base_folder="./data",
        user_id=user_id,
        pattern="*.html",
        parallel=True
    )