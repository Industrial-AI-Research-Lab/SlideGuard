"""
File management utilities for presentation processing.

This module provides functionality for managing presentation files, including
file conversion, image extraction, and caching. It handles various file formats
and maintains a cache for processed files.
"""

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from io import BytesIO
import pypdfium2 as pdfium

import requests
import tiktoken
from PIL import Image

from slideguard.token_manager import TokenManager

# Add parent directory to Python path to enable imports
root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.append(root_dir)


# Constants for OCR processing
OCR_TEXT_BOXES_SEPARATOR_STRING = "\n\n"  # Can be changed to "\n\n" or any other separator

def get_images_from_pdf(file: bytes, target_width: int = 1024, target_height: int = 768):
    pdf = pdfium.PdfDocument(file)

    # Get images
    images = []
    for page_number in range(len(pdf)):
        page = pdf.get_page(page_number)
        bitmap = page.render(scale=2, rotation=0, crop=(0, 0, 0, 0))
        pil_image = bitmap.to_pil()
        resized_pil_image = pil_image.resize((target_width, target_height))

        buffer = BytesIO()
        resized_pil_image.save(buffer, format="JPEG")
        images.append(buffer.getvalue())

    return images

class FileManager:
    """Manager for handling presentation files and their processing.
    
    This class provides functionality for:
    - Converting presentations to images
    - Extracting text and images from presentations
    - Managing a cache of processed files
    - Handling pdf file format
    """

    def __init__(self, cache_dir: str = ".file_cache", llm=None, auto_populate: bool = False):
        """Initialize FileManager with a cache directory to store file mappings.
        
        Args:
            cache_dir: Directory to store cache files
            llm: GigaChat instance for API calls
            auto_populate: If True and cache doesn't exist, automatically populate from server
        """
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "file_mappings.json")
        self._ensure_cache_dir()
        self.file_mappings = self._load_cache()
        self.llm = llm
        self.token_manager = TokenManager(cache_dir)
        self.encoder = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding

        # Auto-populate if enabled and cache is empty
        if auto_populate and not self.file_mappings and llm is not None:
            self.populate_cache_from_server()

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        os.makedirs(self.cache_dir, exist_ok=True)

    def _load_cache(self) -> Dict[str, str]:
        """Load file mappings from cache."""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _get_token_cache_path(self) -> str:
        """Get path to token cache file."""
        cache_dir = os.path.dirname(self.cache_file)
        return os.path.join(cache_dir, 'token_cache.json')

    def _load_cached_token(self) -> Optional[Tuple[str, int]]:
        """Load token and expiry from cache if exists and not expired."""
        cache_path = self._get_token_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                if cache['expires_at'] > time.time() * 1000:  # Convert to milliseconds
                    return cache['access_token'], cache['expires_at']
        return None

    def _save_token_cache(self, token: str, expires_at: int) -> None:
        """Save token and expiry to cache."""
        cache_path = self._get_token_cache_path()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'access_token': token,
                'expires_at': expires_at
            }, f)

    def get_access_token(self) -> str:
        """Get a valid access token, either from cache or by requesting a new one."""
        return self.token_manager.get_access_token()

    def get_file_content(self, file_id: str) -> bytes:
        """Download file content from GigaChat storage."""
        url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
        headers = {
            'Accept': 'image/jpg',
            'Authorization': f'Bearer {self.token_manager.get_access_token()}'
        }
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"Failed to download file content: {response.text}")

    def get_files(self) -> List[dict]:
        """Get list of all available files in GigaChat storage."""
        url = "https://gigachat.devices.sberbank.ru/api/v1/files"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.token_manager.get_access_token()}'
        }
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()['data']
        else:
            raise Exception(f"Failed to get files list: {response.text}")

    def populate_cache_from_server(self) -> None:
        """
        Fetch all files from the server, download them, and populate the cache with their hashes.
        This is useful when cache file is lost or when running on a new machine.
        """
        # Get list of all files from server
        files = self.get_files()
        
        # Process each file
        for file_info in files:
            # Download file content
            file_content = self.get_file_content(file_info['id'])
            
            # Calculate hash
            file_hash = self._calculate_file_hash(file_content)
            
            # Add to cache
            self.file_mappings[file_hash] = file_info
        
        # Save updated cache
        self._save_cache()

    def _save_cache(self):
        """Save file mappings to cache."""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.file_mappings, f)

    def _calculate_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()

    def _uploaded_file_to_dict(self, file):
        """Convert UploadedFile object to a dictionary for JSON serialization"""
        return {
            "id": file.id_,
            "object": file.object_,
            "bytes": file.bytes_,
            "created_at": file.created_at,
            "filename": file.filename,
            "purpose": file.purpose
        }

    def process_presentation(self, llm, presentation_path: str, starting_slide: int = 1, ending_slide: int = None, 
                           use_png: bool = True) -> tuple[str, List[Dict]]:
        """Process a presentation file and upload its slides.
        
        Args:
            llm: The language model instance
            presentation_path: Path to the presentation file
            starting_slide: First slide to process (1-based)
            ending_slide: Last slide to process (inclusive)
            use_png: If True, keep as PNG, if False convert to JPEG
        """
        # First, extract high-quality PNGs using appropriate method
        print(f"Extracting PNGs from {presentation_path}")
        png_dir = self.process_presentation_wrapper(presentation_path)
        
        # Get list of PNG files
        png_files = sorted([f for f in os.listdir(png_dir) if f.endswith('.png')],
                          key=lambda x: int(x.split('_')[1].split('.')[0]))
        
        # Convert to zero-based indices for internal use
        zero_based_start = starting_slide - 1
        zero_based_end = ending_slide
        
        # Validate and adjust slide range
        total_slides = len(png_files)
        if zero_based_start < 0:
            zero_based_start = 0
        
        # Validate end slide
        if zero_based_end is None or zero_based_end < 0 or zero_based_end > total_slides:
            zero_based_end = total_slides
            
        # Get the requested slice of images
        png_files = png_files[zero_based_start:zero_based_end]

        # Create base image cache directory
        base_dir = os.path.dirname(presentation_path)
        image_cache_dir = os.path.join(base_dir, "image_cache")
        os.makedirs(image_cache_dir, exist_ok=True)

        # Process slides and create a combined PDF with OCR where needed
        extracted_content = {}
        with tempfile.TemporaryDirectory() as temp_ocr_dir:
            pdf_path = self.ocr_processor.process_slides_to_pdf(
                png_dir=png_dir,
                png_files=png_files,
                output_dir=temp_ocr_dir,
                base_idx=starting_slide
            )

            # Extract content from the OCR'd PDF for all slides
            all_extracted_content = {}
            if pdf_path and os.path.exists(pdf_path):
                try:
                    all_extracted_content = self.ocr_processor.extract_pdf_content(pdf_path, temp_ocr_dir)
                except Exception as e:
                    print(f"Error extracting content from OCR'd PDF: {str(e)}")

            # Process per slide: if a slide has insufficient OCR content, run individual OCR
            for slide_idx in range(starting_slide, zero_based_end + 1):
                # Map from user slide number to sequential OCR number (1-based)
                ocr_idx = slide_idx - starting_slide + 1
                content = all_extracted_content.get(ocr_idx, "")
                if not content or len(content.strip()) < 3:
                    print(f"Slide {slide_idx}: insufficient OCR content, processing individually.")
                    try:
                        # Get the corresponding PNG file for this slide
                        png_file = png_files[slide_idx - starting_slide]
                        # Process individual slide
                        single_slide_pdf = self.ocr_processor.process_slides_to_pdf(
                            png_dir=png_dir,
                            png_files=[png_file],
                            output_dir=temp_ocr_dir,
                            base_idx=1  # Single slide, so base index is 1
                        )
                        if single_slide_pdf and os.path.exists(single_slide_pdf):
                            try:
                                temp_content = self.ocr_processor.extract_pdf_content(single_slide_pdf, temp_ocr_dir)
                                # Get the JSON content from the first page
                                json_file = os.path.join(temp_ocr_dir, "json", "page_1.json")
                                if os.path.exists(json_file):
                                    with open(json_file, 'r', encoding='utf-8') as f:
                                        slide_ocr = json.load(f)
                                else:
                                    slide_ocr = {"raw_text": temp_content.get("page_1", "")}
                            except Exception as e:
                                print(f"Error extracting OCR content for slide {slide_idx}: {str(e)}")
                                slide_ocr = {}
                    except Exception as e:
                        print(f"Error extracting OCR content for slide {slide_idx}: {str(e)}")
                        slide_ocr = ""
                extracted_content[slide_idx] = content

        uploaded_files = []
        print(f"Processing and uploading {len(png_files)} slides...")
        with tempfile.TemporaryDirectory() as tmpdirname:
            # Process each PNG file
            for idx, png_file in enumerate(png_files):
                # Use 1-based slide number for the filename
                slide_num = starting_slide + idx
                source_path = os.path.join(png_dir, png_file)
                
                # Determine output format and path
                extension = "png" if use_png else "jpeg"
                temp_output_path = os.path.join(tmpdirname, f"img_{slide_num}.{extension}")
                
                # Open and optionally convert the image
                img = Image.open(source_path)
                
                if use_png:
                    # Just copy the PNG file
                    shutil.copy2(source_path, temp_output_path)
                else:
                    # Convert to JPEG with high quality
                    img.save(temp_output_path, format='JPEG', quality=99)
                
                # Calculate hash for the image
                with open(temp_output_path, 'rb') as f:
                    image_hash = self._calculate_file_hash(f.read())
                
                # Create hash-specific directory
                hash_dir = os.path.join(image_cache_dir, image_hash)
                os.makedirs(hash_dir, exist_ok=True)
                
                # Define final paths in hash directory
                final_image_path = os.path.join(hash_dir, f"image.{extension}")
                ocr_path = os.path.join(hash_dir, "ocr_data.json")
                
                # Check if we already have this image processed
                if os.path.exists(final_image_path) and os.path.exists(ocr_path):
                    print(f"Using cached files from: {hash_dir}")
                    # Load existing OCR data
                    with open(ocr_path, 'r', encoding='utf-8') as f:
                        slide_ocr = json.load(f)
                else:
                    # Move image to hash directory
                    shutil.move(temp_output_path, final_image_path)
                    
                    # Get OCR data from extracted content or process with OCR
                    slide_ocr = extracted_content.get(int(slide_num), "")
                    if not slide_ocr:
                        print(f"Processing OCR for slide {slide_num}...")
                        # Create temporary PDF with OCR
                        with tempfile.TemporaryDirectory() as temp_ocr_dir:
                            temp_pdf = os.path.join(temp_ocr_dir, f"temp_slide_{slide_num}.pdf")
                            if self.ocr_processor.process_image_slide(final_image_path, temp_pdf):
                                try:
                                    temp_content = self.ocr_processor.extract_pdf_content(temp_pdf, temp_ocr_dir)
                                    # Get the JSON content from the first page
                                    json_file = os.path.join(temp_ocr_dir, "json", "page_1.json")
                                    if os.path.exists(json_file):
                                        with open(json_file, 'r', encoding='utf-8') as f:
                                            slide_ocr = json.load(f)
                                    else:
                                        slide_ocr = {"raw_text": temp_content.get("page_1", "")}
                                except Exception as e:
                                    print(f"Error extracting OCR content: {str(e)}")
                                    slide_ocr = {}
                    
                    # Validate and process slide_ocr
                    if not isinstance(slide_ocr, dict):
                        # If slide_ocr is not a dict (not JSON), wrap it in a dict with raw_text
                        slide_ocr = {"raw_text": str(slide_ocr)}
                    
                    # Save OCR data in hash directory
                    with open(ocr_path, 'w', encoding='utf-8') as f:
                        json.dump(slide_ocr, f, ensure_ascii=False, indent=2)
                    
                    # Save plain text version
                    text_path = os.path.join(hash_dir, "ocr_data_text.txt")
                    with open(text_path, 'w', encoding='utf-8') as f:
                        if 'text_boxes' in slide_ocr:
                            # Extract text from each text box and join with the separator
                            texts = [box['text'] for box in slide_ocr['text_boxes']]
                            f.write(OCR_TEXT_BOXES_SEPARATOR_STRING.join(texts))
                        elif 'raw_text' in slide_ocr:
                            f.write(slide_ocr['raw_text'])
                        else:
                            # If no recognized format, write empty string
                            f.write("")
                
                # Check if already uploaded to GigaChat
                if image_hash in self.file_mappings:
                    print(f"Image already uploaded with ID: {self.file_mappings[image_hash]['id']}")
                    file_dict = self.file_mappings[image_hash]
                    file_dict['ocr_file'] = ocr_path
                    file_dict['image_file'] = final_image_path
                    uploaded_files.append(file_dict)
                    continue

                # Upload new image
                with open(final_image_path, "rb") as f:
                    print(f"Uploading slide {slide_num} to GigaChat...")
                    uploaded_file = llm.upload_file(f)
                
                # Convert UploadedFile to dictionary and add OCR path
                file_dict = self._uploaded_file_to_dict(uploaded_file)
                file_dict['ocr_file'] = ocr_path
                file_dict['image_file'] = final_image_path
                
                # Store mapping
                self.file_mappings[image_hash] = file_dict
                uploaded_files.append(file_dict)

        # Save updated cache
        self._save_cache()
        
        return png_dir, uploaded_files

    def get_presentation_ids(self, presentation_path: str, max_slides: Optional[int] = None) -> List[str]:
        """
        Get list of file IDs for a presentation's slides.
        Returns empty list if presentation hasn't been processed yet.
        """
        with open(presentation_path, "rb") as f:
            file_content = f.read()

        images = get_images_from_pdf(file_content)
        if max_slides:
            images = images[:max_slides]

        file_ids = []
        for image in images:
            image_hash = self._calculate_file_hash(image)
            if image_hash in self.file_mappings:
                file_ids.append(self.file_mappings[image_hash]['id'])

        return file_ids

    def upload_file(self, file_or_path, llm=None) -> dict:
        """
        Upload a single file if it hasn't been uploaded before.
        
        Args:
            file_or_path: Either a file-like object or a path to file
            llm: Optional GigaChat instance. If not provided, uses the one from initialization.
            
        Returns:
            Uploaded file dictionary
        """
        llm = llm or self.llm
        if llm is None:
            raise ValueError("LLM instance must be provided either during initialization or when calling this method")

        # If string path provided, open the file
        if isinstance(file_or_path, str):
            with open(file_or_path, 'rb') as f:
                content = f.read()
        else:
            # Read content from file-like object
            content = file_or_path.read()
            # Reset file pointer if possible
            if hasattr(file_or_path, 'seek'):
                file_or_path.seek(0)

        # Calculate hash of content
        file_hash = self._calculate_file_hash(content)
        
        # Check if we already have this file
        if file_hash in self.file_mappings:
            print(f"Found cached file with ID: {self.file_mappings[file_hash]['id']}")
            return self.file_mappings[file_hash]
            
        # Upload new file
        if isinstance(file_or_path, str): 
            with open(file_or_path, 'rb') as f:
                uploaded_file = llm.upload_file(f)
        else:
            uploaded_file = llm.upload_file(file_or_path)
            
        # Store in cache
        self.file_mappings[file_hash] = {
            'id': uploaded_file.id_,
            'ocr_file': None,
            'image_file': None
        }
        self._save_cache()
        
        return self.file_mappings[file_hash]

    def _calculate_presentation_hash(self, presentation_path: str) -> str:
        """Calculate hash of presentation file for caching"""
        with open(presentation_path, 'rb') as f:
            return self._calculate_file_hash(f.read())
    
    def _verify_png_slides(self, png_dir: str, total_slides: int) -> bool:
        """Verify that all slides are present in the PNG directory"""
        for i in range(1, total_slides + 1):
            if not os.path.exists(os.path.join(png_dir, f'slide_{i}.png')):
                return False
        return True

    def process_presentation_from_pdf(self, presentation_path: str, output_dir: str) -> None:
        """Process PDF presentation and extract high-quality PNG images"""
        try:
            # Read PDF content
            with open(presentation_path, 'rb') as f:
                pdf_content = f.read()

            # Get images from PDF
            images = get_images_from_pdf(pdf_content)

            # Save each image
            for i, image_data in enumerate(images, 1):
                output_path = os.path.join(output_dir, f"slide_{i}.png")
                with open(output_path, 'wb') as f:
                    f.write(image_data)

        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            raise

    def process_presentation_wrapper(self, presentation_path: str) -> str:
        """Process presentation file PDF and extract high-quality PNG images"""
        if not os.path.exists(presentation_path):
            raise FileNotFoundError(f"Presentation file not found: {presentation_path}")

        # Create base png directory if it doesn't exist
        base_dir = os.path.dirname(presentation_path)
        png_dir = os.path.join(base_dir, "png")
        if not os.path.exists(png_dir):
            os.makedirs(png_dir)

        # Calculate presentation hash for unique directory
        presentation_hash = self._calculate_presentation_hash(presentation_path)
        output_dir = os.path.join(png_dir, presentation_hash)
        os.makedirs(output_dir, exist_ok=True)

        # Determine file type and process accordingly
        file_ext = os.path.splitext(presentation_path)[1].lower()
        if file_ext == '.pdf':
            self.process_presentation_from_pdf(presentation_path, output_dir)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        return output_dir

    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text using tiktoken."""
        return len(self.encoder.encode(text))

    def get_slides_descriptions(self, presentation_path: str, start_slide: int = 1, end_slide: int = None, max_tokens: Optional[int] = None) -> List[str]:
        """Concatenate descriptions from selected slides in a presentation.
        
        Args:
            presentation_path: Path to the presentation file
            start_slide: First slide number to include (1-based indexing)
            end_slide: Last slide number to include. If None, includes all slides
            max_tokens: Maximum number of tokens per chunk. If None, no limit
            
        Returns:
            List[str]: List of results, each element contains descriptions up to max_tokens
        """
        # Get presentation hash
        presentation_hash = self._calculate_presentation_hash(presentation_path)
        
        # Find all PNG files and sort them by slide number
        png_dir = os.path.join(os.path.dirname(presentation_path), "png", presentation_hash)
        if not os.path.exists(png_dir):
            raise ValueError(f"PNG directory not found: {png_dir}")
            
        png_files = sorted(
            [f for f in os.listdir(png_dir) if f.endswith('.png') and f.startswith('slide_')],
            key=lambda x: int(x.split('_')[1].split('.')[0])
        )
        
        # Convert to zero-based indices for internal use
        zero_based_start = start_slide - 1
        zero_based_end = end_slide
        
        # Validate and adjust slide range
        total_slides = len(png_files)
        if zero_based_start < 0:
            zero_based_start = 0
        
        # Validate end slide
        if zero_based_end is None or zero_based_end < 0 or zero_based_end > total_slides:
            zero_based_end = total_slides
            
        # Get the requested slice of images
        png_files = png_files[zero_based_start:zero_based_end]

        if not png_files:
            return ["Нет слайдов в указанном диапазоне"]
        
        results = []
        current_chunk = ["Вот общая информация по каждому слайду"]
        current_tokens = self._count_tokens("\n".join(current_chunk))
        
        for png_file in png_files:
            slide_num = int(png_file.split('_')[1].split('.')[0])
            
            # Calculate image hash for the slide
            with open(os.path.join(png_dir, png_file), 'rb') as f:
                image_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Get description file path
            desc_file = os.path.join(
                os.path.dirname(presentation_path),
                "image_cache",
                image_hash,
                "0_1_slide_description.txt"
            )
            
            # Prepare slide content
            slide_content = []
            slide_content.append(f"Слайд {slide_num}")
            slide_content.append("```")
            
            if os.path.exists(desc_file):
                try:
                    with open(desc_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        slide_content.append(content)
                except Exception as e:
                    slide_content.append(f"Ошибка чтения описания: {str(e)}")
            else:
                slide_content.append("Описание отсутствует")
            
            slide_content.append("```")
            
            # Calculate tokens for this slide
            slide_text = "\n".join(slide_content)
            slide_tokens = self._count_tokens(slide_text)
            
            # Check if adding this slide would exceed max_tokens
            if max_tokens is not None and current_tokens + slide_tokens > max_tokens:
                # Save current chunk and start a new one
                results.append("\n".join(current_chunk))
                current_chunk = ["Вот общая информация по каждому слайду"]
                current_tokens = self._count_tokens("\n".join(current_chunk))
            
            # Add slide content to current chunk
            current_chunk.extend(slide_content)
            current_tokens += slide_tokens
        
        # Add the last chunk if it's not empty
        if current_chunk:
            results.append("\n".join(current_chunk))
        
        return results if results else ["Нет слайдов в указанном диапазоне"]

    def get_slide_image_bytes(self, image_url: str, img_dir: Optional[str] = None) -> Optional[bytes]:
        """Retrieve image bytes from a slide image URL/ID.
        
        This method handles different types of image references:
        - Base64 data URLs (data:image/...)
        - File IDs that need to be resolved through file_mappings
        - Direct file paths
        
        Args:
            image_url: Image URL/ID from SlideData.image field
            img_dir: Optional image directory path for fallback lookup
            
        Returns:
            Image bytes if found, None otherwise
        """
        if not image_url:
            return None
            
        try:
            # Handle base64 data URLs
            if image_url.startswith('data:image/'):
                # Extract base64 data after the comma
                if ',' in image_url:
                    base64_data = image_url.split(',', 1)[1]
                    return base64.b64decode(base64_data)
                else:
                    print(f"Invalid base64 data URL format: {image_url}")
                    return None
            
            # Handle direct file paths
            if os.path.isfile(image_url):
                with open(image_url, 'rb') as f:
                    return f.read()
            
            # Handle file IDs - look up in file_mappings
            for file_hash, file_info in self.file_mappings.items():
                if file_info.get('id') == image_url:
                    # Found the file ID, get the image file path
                    image_file = file_info.get('image_file')
                    if image_file and os.path.exists(image_file):
                        with open(image_file, 'rb') as f:
                            return f.read()
                    else:
                        print(f"Image file not found for file ID {image_url}: {image_file}")
                    break
            
            # Fallback: try to find image in img_dir by treating image_url as filename or slide number
            if img_dir and os.path.isdir(img_dir):
                # Try common slide naming patterns
                possible_names = [
                    image_url,
                    f"{image_url}.png",
                    f"{image_url}.jpg", 
                    f"{image_url}.jpeg",
                    f"slide_{image_url}.png",
                    f"slide_{image_url}.jpg"
                ]
                
                # If image_url is numeric, try slide numbering patterns
                if image_url.isdigit():
                    slide_num = int(image_url)
                    possible_names.extend([
                        f"slide_{slide_num + 1}.png",  # 1-based indexing
                        f"slide_{slide_num + 1}.jpg",
                        f"img_{slide_num + 1}.png",
                        f"img_{slide_num + 1}.jpg"
                    ])
                
                for name in possible_names:
                    file_path = os.path.join(img_dir, name)
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            return f.read()
            
            print(f"Could not resolve image URL to file: {image_url}")
            return None
            
        except Exception as e:
            print(f"Error retrieving image bytes for {image_url}: {str(e)}")
            return None
