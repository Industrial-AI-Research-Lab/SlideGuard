"""
File management utilities for presentation processing.

This module provides functionality for managing presentation files, including
file conversion, image extraction, and caching. It handles various file formats
and maintains a cache for processed files.
"""

import hashlib
import logging
import os
import shutil
import time
from typing import Dict, Optional
from io import BytesIO
import pypdfium2 as pdfium

from slideguard.schemes import SlideDeckImages, SlideImage

from pydantic import BaseModel


logger = logging.getLogger(__name__)


class FileCacheEntry(BaseModel):
    """Pydantic model for cache entries."""
    file_hash: str
    output_dir: str
    presentation_path: str
    processed_at: float


class FileCache(BaseModel):
    """Pydantic model for file cache."""
    file_mappings: Dict[str, FileCacheEntry]


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

    def __init__(self, cache_dir: str = ".slideguard_cache/file_cache"):
        """Initialize FileManager with a cache directory to store file mappings.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "file_mappings.json")
        self.cache_decks_dir = os.path.join(cache_dir, "png")
        self.file_mappings = self._load_cache()

    def _load_cache(self) -> Dict[str, FileCacheEntry]:
        """Load file mappings from cache."""
        
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.cache_decks_dir, exist_ok=True)

        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.file_mappings = FileCache.model_validate_json(f.read())
        else:
            self.file_mappings = FileCache(file_mappings=dict())
        
        return self.file_mappings

    def _get_cache_entry(self, cache_key: str) -> Optional[FileCacheEntry]:
        """Get a cache entry by key.
        
        Args:
            cache_key: The cache key to look up
            
        Returns:
            CacheEntry if found, None otherwise
        """
        return self.file_mappings.file_mappings.get(cache_key, None)

    def _upsert_cache_entry(self, cache_key: str, cache_entry: FileCacheEntry) -> None:
        """Insert or update a cache entry.
        
        Args:
            cache_key: The cache key
            cache_entry: The cache entry to store
        """
        self.file_mappings.file_mappings[cache_key] = cache_entry

        with open(self.cache_file, 'w', encoding='utf-8') as f:
            f.write(self.file_mappings.model_dump_json())

    def process_presentation(self, presentation_path: str):
        """Process a presentation file and extract PNG images to cache.
        
        Args:
            presentation_path: Path to the presentation file
            
        Returns:
            SlideDeckImages: Object containing PNG directory path and slide information
        """
        
        if not os.path.exists(presentation_path):
            raise FileNotFoundError(f"Presentation file not found: {presentation_path}")
        
        if not os.path.isfile(presentation_path):
            raise ValueError(f"Presentation path is a directory: {presentation_path}")

        file_ext = os.path.splitext(presentation_path)[1].lower()
        if file_ext != '.pdf':
            raise ValueError(f"Unsupported file type: {file_ext}")

        # Calculate presentation hash for cache validation
        cache_key = self._calculate_presentation_hash(presentation_path)
        
        # Create hash-specific output directory
        output_dir = os.path.join(self.cache_decks_dir, os.path.basename(presentation_path))
        
        # Check if presentation is already cached and valid
        cache_entry = self._get_cache_entry(cache_key)
        cache_valid = (
            os.path.exists(output_dir) 
            and cache_entry is not None
            and cache_entry.file_hash == cache_key
        )
        if not cache_valid:
            logger.info(f"Removing invalid cache: {output_dir}")
            shutil.rmtree(output_dir, ignore_errors=True)
            os.makedirs(output_dir, exist_ok=True)
            
            # Extract images from presentation
            logger.info(f"Extracting images from {presentation_path}")
            self._process_presentation_from_pdf(presentation_path, output_dir)
            
            # Update cache with presentation info
            new_cache_entry = FileCacheEntry(
                file_hash=cache_key,
                output_dir=output_dir,
                presentation_path=presentation_path,
                processed_at=time.time()
            )
            self._upsert_cache_entry(cache_key, new_cache_entry)
        
        # Get list of PNG files and create slide objects
        png_files = (f for f in os.listdir(output_dir) if f.endswith('.png'))
        
        slides = (
            SlideImage(
                slide_id=int(png_file.split('_')[1].split('.')[0]),
                slide_image_path=os.path.join(output_dir, png_file)
            )
            for png_file in png_files
        )
        slides = sorted(slides, key=lambda x: x.slide_id)
        
        return SlideDeckImages(
            png_dir=output_dir,
            slide_deck_path=presentation_path,
            slides=slides
        )

    def _calculate_presentation_hash(self, presentation_path: str) -> str:
        """Calculate hash of presentation file for caching"""
        with open(presentation_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _process_presentation_from_pdf(self, presentation_path: str, output_dir: str) -> None:
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
            logger.error(f"Error processing PDF: {str(e)}")
            raise
