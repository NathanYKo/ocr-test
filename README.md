# Directory OCR

This project extracts structured data from historical directory images using OCR and Python.

## Requirements

- Python 3.8+
- Tesseract OCR (installed and in your PATH)
- The following Python packages:
  - opencv-python
  - numpy
  - pytesseract
  - Pillow
  - pandas
  - spacy

## Setup

1. **Clone the repository and navigate to the project directory.**

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the spaCy English model:**
   ```bash
   python -m spacy download en_core_web_sm
   ```

4. **Install Tesseract OCR:**
   - **Windows:** [Download here](https://github.com/UB-Mannheim/tesseract/wiki) and add the install directory (e.g., `C:\Program Files\Tesseract-OCR`) to your PATH.
   - **macOS:**
     ```bash
     brew install tesseract
     ```
   - **Linux:**
     ```bash
     sudo apt-get install tesseract-ocr
     ```

## Usage

1. **Place your directory images in the `minesota-sample-data` folder.**
   - Update the image path in `directory_ocr.py` if needed.

2. **Run the script:**
   ```bash
   python directory_ocr.py
   ```

3. **Output:**
   - The script prints parsed entries to the console.
   - It saves a CSV file named `test_output.csv` with columns: `last`, `first`, `occupation`, `home_addr`.

