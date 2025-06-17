import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
import pandas as pd
import spacy
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DirectoryProcessor:
    def __init__(self):
        # Load spaCy model for NLP tasks
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("Downloading spaCy model...")
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

    def preprocess_image(self, image_path):
        """Preprocess the image: deskew, denoise, and binarize."""
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        # Save original image for debugging
        cv2.imwrite('debug_original.png', img)
        logger.info("Saved original image as debug_original.png")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite('debug_gray.png', gray)
        logger.info("Saved grayscale image as debug_gray.png")

        # Apply adaptive thresholding instead of global
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,  # Block size
            2    # C constant
        )
        cv2.imwrite('debug_binary.png', binary)
        logger.info("Saved binary image as debug_binary.png")

        # Try to improve contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        cv2.imwrite('debug_enhanced.png', enhanced)
        logger.info("Saved enhanced image as debug_enhanced.png")

        # Try OCR on both binary and enhanced images
        logger.info("Testing OCR on binary image...")
        binary_text = pytesseract.image_to_string(binary)
        logger.info(f"Binary image OCR result: {binary_text[:200]}")

        logger.info("Testing OCR on enhanced image...")
        enhanced_text = pytesseract.image_to_string(enhanced)
        logger.info(f"Enhanced image OCR result: {enhanced_text[:200]}")

        # Return the image that gave better results
        if len(binary_text) > len(enhanced_text):
            logger.info("Using binary image for processing")
            return binary
        else:
            logger.info("Using enhanced image for processing")
            return enhanced

    def extract_year_from_header(self, image):
        """Extract the year from the header of the directory."""
        # Crop the top portion of the image
        height = image.shape[0]
        header = image[:height//10, :]
        
        # OCR the header
        header_text = pytesseract.image_to_string(header)
        
        # Look for year pattern
        year_match = re.search(r'\b(19|20)\d{2}\b', header_text)
        if year_match:
            return year_match.group(0)
        return None

    def process_directory_page(self, image_path):
        """Process a single directory page and extract entries."""
        # Preprocess image
        processed_image = self.preprocess_image(image_path)
        
        # Extract year from header
        year = self.extract_year_from_header(processed_image)
        
        # Get HOCR output
        hocr = pytesseract.image_to_pdf_or_hocr(processed_image, extension='hocr')
        
        # Parse entries
        entries = self.parse_entries(hocr)
        
        # Add year to each entry
        for entry in entries:
            entry['year'] = year
            
        return entries

    def parse_entries(self, hocr):
        """Parse HOCR output into structured entries."""
        entries = []
        current_entry = None
        
        # Regular expressions for field extraction
        name_pattern = re.compile(r'^(?P<last>[A-Za-z\'\-\s]+),\s*(?P<first>[A-Za-z\.\s]+?)(?:\s*(?:&|and)\s*(?P<spouse>[A-Za-z\.\s]+))?(?=,|\s)')
        occupation_pattern = re.compile(r',\s*(?P<occupation>[^,]+?)(?=,|\s+h\b)')
        address_pattern = re.compile(r'(?:h(?:ouse)?|bds|res)\s+(?P<address>[^,\.]+)')
        
        # Debug: Print raw HOCR output
        logger.info("Raw HOCR output:")
        logger.info(hocr.decode('utf-8')[:1000])  # Print first 1000 chars for debugging
        
        # Process HOCR output line by line
        for line in hocr.decode('utf-8').split('\n'):
            if 'ocr_line' in line:
                text = re.search(r'>([^<]+)<', line)
                if text:
                    text = text.group(1).strip()
                    logger.info(f"Processing line: {text}")  # Debug: Print each line being processed
                    
                    # Skip page breaks and section headers
                    if text in ['—o—', 'ST. ANTHONY.', 'B']:
                        logger.info(f"Skipping header/break: {text}")
                        continue
                    
                    # Check if this is a new entry (starts with capitalized last name)
                    name_match = name_pattern.match(text)
                    if name_match:
                        logger.info(f"Found name match: {text}")  # Debug: Print when name is found
                        if current_entry:
                            entries.append(current_entry)
                            logger.info(f"Added entry: {current_entry}")  # Debug: Print when entry is added
                        current_entry = {
                            'last_name': name_match.group('last').strip(),
                            'first_name': name_match.group('first').strip(),
                            'spouse_name': name_match.group('spouse').strip() if name_match.group('spouse') else None
                        }
                        
                        # Extract occupation if present
                        occ_match = occupation_pattern.search(text)
                        if occ_match:
                            current_entry['occupation'] = occ_match.group('occupation').strip()
                            logger.info(f"Found occupation: {current_entry['occupation']}")
                        
                        # Extract address if present
                        addr_match = address_pattern.search(text)
                        if addr_match:
                            current_entry['home_address'] = addr_match.group('address').strip()
                            if 'bds' in text:
                                current_entry['residence_type'] = 'boards'
                            else:
                                current_entry['residence_type'] = 'home'
                            logger.info(f"Found address: {current_entry['home_address']}")
        
        # Add the last entry
        if current_entry:
            entries.append(current_entry)
            logger.info(f"Added final entry: {current_entry}")
        
        logger.info(f"Total entries found: {len(entries)}")
        return entries

    def process_directory(self, input_dir, output_file):
        """Process all directory pages in a directory and save results."""
        all_entries = []
        
        # Process each image in the directory
        for image_path in Path(input_dir).glob('*.jpg'):
            try:
                entries = self.process_directory_page(image_path)
                all_entries.extend(entries)
            except Exception as e:
                logger.error(f"Error processing {image_path}: {str(e)}")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(all_entries)
        df.to_csv(output_file, index=False)
        logger.info(f"Processed {len(all_entries)} entries. Results saved to {output_file}")

    def test_single_image(self, image_path):
        """Process a single image and print the results."""
        try:
            logger.info(f"Processing single image: {image_path}")
            
            # Check if file exists
            if not Path(image_path).exists():
                logger.error(f"Image file does not exist: {image_path}")
                return None
                
            # Preprocess image
            logger.info("Starting image preprocessing...")
            processed_image = self.preprocess_image(image_path)
            logger.info("Image preprocessing completed")
            
            # Try different OCR configurations
            logger.info("Running OCR with different configurations...")
            
            # Try with different PSM modes
            psm_modes = [3, 4, 6]  # Different page segmentation modes
            best_hocr = None
            best_text = ""
            
            for psm in psm_modes:
                logger.info(f"Trying PSM mode {psm}...")
                custom_config = f'--psm {psm} --oem 3'
                hocr = pytesseract.image_to_pdf_or_hocr(processed_image, extension='hocr', config=custom_config)
                text = pytesseract.image_to_string(processed_image, config=custom_config)
                
                if len(text) > len(best_text):
                    best_text = text
                    best_hocr = hocr
                    logger.info(f"Found better results with PSM {psm}")
                    logger.info(f"Sample text: {text[:200]}")
            
            if not best_hocr:
                logger.error("No text was detected with any OCR configuration")
                return None

            # Print the full OCR text output for debugging
            print("\n===== FULL OCR TEXT OUTPUT (Best PSM) =====\n")
            print(best_text)
            print("\n===== END OCR TEXT OUTPUT =====\n")

            # Parse entries from plain text
            print("\n===== PARSED ENTRIES FROM OCR TEXT =====\n")
            entries = self.parse_entries_from_text(best_text)
            for entry in entries:
                print(entry)
            print("\n===== END PARSED ENTRIES =====\n")

            # Optionally, save to CSV
            if entries:
                df = pd.DataFrame(entries)
                output_file = "test_output.csv"
                df.to_csv(output_file, index=False)
                logger.info(f"Saved {len(entries)} entries to {output_file}")
            else:
                logger.warning("No entries parsed from OCR text!")
            return entries
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def segment_entries(self, text):
        """Segment OCR text into individual entries, handling multi-line entries."""
        import re
        entries = []
        current_entry = ''
        # Pattern: line starts with capitalized word + comma
        entry_start = re.compile(r"^[A-Z][A-Za-z'\'\- ]+,")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('CITY DIRECTORY') or line.startswith('—:0:') or line.startswith('ST. ANTHONY.') or line == 'B':
                continue
            if entry_start.match(line):
                if current_entry:
                    entries.append(current_entry.strip())
                current_entry = line
            else:
                # Continuation of previous entry (multi-line)
                if current_entry:
                    current_entry += ' ' + line
                else:
                    current_entry = line
        if current_entry:
            entries.append(current_entry.strip())
        return entries

    def extract_fields_from_entry(self, entry, occupation_list=None):
        """Extract only last, first, occupation, and home_addr from a single entry string using regex and heuristics."""
        import re
        # Last, First (and Spouse)
        name_match = re.match(r"^(?P<last>[A-Za-z'\- ]+),\s*(?P<first>[A-Za-z\. ]+)(?:\s*(?:&|and)\s*[A-Za-z\. ]+)?", entry)
        if not name_match:
            return None
        result = name_match.groupdict()
        rest = entry[name_match.end():].strip(' ,.')

        # Occupation (if present)
        occupation = None
        if occupation_list:
            for occ in occupation_list:
                if rest.lower().startswith(occ):
                    occupation = occ
                    rest = rest[len(occ):].strip(' ,.')
                    break
        else:
            occ_match = re.match(r"([^,]+)", rest)
            if occ_match:
                occupation = occ_match.group(1)
                rest = rest[occ_match.end():].strip(' ,.')
        result['occupation'] = occupation

        # Home address (after h/house/bds)
        home_addr = None
        res_match = re.search(r'(?:h|house|bds)\s+([^,\.]+)', rest)
        if res_match:
            home_addr = res_match.group(1)
        result['home_addr'] = home_addr

        # Only keep the required fields
        return {
            'last': result.get('last'),
            'first': result.get('first'),
            'occupation': result.get('occupation'),
            'home_addr': result.get('home_addr')
        }

    def parse_entries_from_text(self, text):
        """Segment text into entries and extract fields from each entry."""
        # Optionally, you can build a more complete occupation list
        occupation_list = [
            'laborer', 'painter', 'porter', 'proprietor', 'clerk', 'watchman', 'lumberman', 'speculator',
            'judge', 'maker', 'mill-wright', 'associate', 'dep. reg. of deeds', 'carriage maker', 'baker',
            'basket maker', 'engineer', 'teacher', 'farmer', 'blacksmith', 'shoemaker', 'deputy', 'porter'
        ]
        occupation_list = [o.lower() for o in occupation_list]
        entries = []
        entry_blobs = self.segment_entries(text)
        for blob in entry_blobs:
            fields = self.extract_fields_from_entry(blob, occupation_list=occupation_list)
            if fields:
                entries.append(fields)
        return entries

if __name__ == "__main__":
    processor = DirectoryProcessor()
    # Test with a single image
    test_image = r"C:\Users\knath\OneDrive\Documents\GitHub\OCR trying\minesota-sample-data\Screenshot 2025-06-17 140432.png"
    processor.test_single_image(test_image) 