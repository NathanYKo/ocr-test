import easyocr
import re

def extract_resident_data_from_entry(entry):
    entry = entry.strip()
    if not entry:
        return None
    pattern = re.compile(r"""
        ^\s*
        (?P<last_name>[^,]+),\s*                # Last name before first comma
        (?P<first_name>[^,]+),\s*               # First name/initials before next comma
        (?P<occupation>[^,]+?),\s*              # Occupation before next comma (non-greedy)
        (?P<residence_indicator>h|bds)\s+       # Residence indicator (h or bds)
        (?P<home_address>[^.]+?)                 # Address up to period or end
        [\.]?\s*$                              # Optional period and end of line
    """, re.VERBOSE | re.IGNORECASE)
    match = pattern.match(entry)
    if match:
        data = match.groupdict()
    else:
        fallback = re.match(r"^\s*([^,]+),\s*([^,]+),\s*([^,]+),?\s*(h|bds)?\s*([^.]*)", entry)
        data = {
            'last_name': fallback.group(1) if fallback else None,
            'first_name': fallback.group(2) if fallback else None,
            'occupation': fallback.group(3) if fallback else None,
            'residence_indicator': fallback.group(4) if fallback and fallback.group(4) else None,
            'home_address': fallback.group(5).strip() if fallback and fallback.group(5) else None
        }
    spouse_match = re.search(r'wife(?: of)? ([A-Za-z .]+)', entry, re.IGNORECASE)
    data['spouse_name'] = spouse_match.group(1) if spouse_match else None
    business_match = re.search(r'(office|works for|proprietor|company|firm)[^.,]*[.,]', entry, re.IGNORECASE)
    data['business_name'] = business_match.group(0).strip('.,') if business_match else None
    year_match = re.search(r'\b(18|19|20)\d{2}\b', entry)
    data['year'] = year_match.group(0) if year_match else None
    return data

def segment_entries(lines):
    entries = []
    current_entry = ''
    entry_start_pattern = re.compile(r'^[A-Z][a-zA-Z]+,')
    skip_patterns = [
        re.compile(r'^[-–—oO]+$'),  # page-break marker
        re.compile(r'^[A-Z][A-Z. ]+$'),  # section headers (all caps, possibly with periods/spaces)
        re.compile(r'^[A-Z]$'),  # single capital letter (section)
    ]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(p.match(line) for p in skip_patterns):
            continue
        if entry_start_pattern.match(line):
            if current_entry:
                entries.append(current_entry.strip())
            current_entry = line
        else:
            if current_entry:
                current_entry += ' ' + line
            else:
                current_entry = line
    if current_entry:
        entries.append(current_entry.strip())
    return entries

path = r'C:\Users\knath\OneDrive\Documents\GitHub\OCR trying\minesota-sample-data\Screenshot 2025-06-17 140432.png'
reader = easyocr.Reader(['en'])
result = reader.readtext(path)

if __name__ == "__main__":
    print("\nExtracted Resident Data (per entry):")
    print("-" * 60)
    # Join all OCR text blocks into one string, then split into lines
    all_text = '\n'.join([detection[1] for detection in result if detection[2] > 0.5])
    lines = all_text.split('\n')
    entries = segment_entries(lines)
    for entry in entries:
        data = extract_resident_data_from_entry(entry)
        if data and any(data.values()):
            print(f"Entry: {entry.strip()}")
            for key, value in data.items():
                if value:
                    print(f"  {key.replace('_', ' ').title()}: {value}")
            print("-" * 60)
