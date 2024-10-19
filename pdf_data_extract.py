import pandas as pd
import re
import fitz  # PyMuPDF
import json
from pdfminer.high_level import extract_text

# Step 1: Read test names from CSV
def read_test_names(csv_file):
    df = pd.read_csv(csv_file)
    return df['Test_Name'].tolist()  # Adjust the column name as necessary

# Step 2: Extract text from PDF
def extract_text_from_pdf(pdf_file):
    text = ''
    try:
        pdf_document = fitz.open(pdf_file)
        num_pages = pdf_document.page_count
        for page_number in range(num_pages):
            page = pdf_document.load_page(page_number)
            # Extract text blocks and sort them
            blocks = page.get_text("blocks")
            blocks_sorted = sorted(blocks, key=lambda b: (b[1], b[0]))
            for block in blocks_sorted:
                text= text + block[4]
    except Exception as e:
        print(f"Error: {e}")
    return text

# Step 3: Search for test names and extract results
default_units = {
    'Hemoglobin': 'gm%',
    'Total WBC Count': 'Cells/cumm',
    'RBC Count': 'Millions/cumm',
    'RDW': '%',
    'HCT': '%',
    'MCV': 'fL',
    'MCH': 'pg',
    'MCHC': 'g/dL',
    'MPV': 'fL',
    'Lymphocytes': '%',
    'Neutrophils': '%',
    'Basophils': '%',
    'Eosinophils': '%',
    'Monocytes': '%',
    'Platelet Count': 'Laks/cumm',
    'Vitamin D 25 - Hydroxy': 'ng/mL',
    'Vitamin B12': 'pg/mL',
    'Fasting Plasma Glucose': 'mg/dL',
    'Total Cholesterol': 'mg/dL',
    'Cholesterol / HDL Ratio': None,
    'Plasma Glucose': 'mg/dL',
    # Add other relevant tests and their units
}

def extract_demography_from_pdf(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    #print(text)
    # Step 2: Define regex pattern for Name
    # This pattern accounts for optional titles (Mr., Ms., etc.) and handles tabs and spaces
    name_pattern = r'(?i)Name\s*[:\t]*\s*(?:Mr\.|Ms\.|Mrs\.|Dr\.)?\s*([A-Za-z\s]+)(?=\n)'
    age_gender_pattern = r'(?i)Age\s*/?\s*Gender\s*[:\t]*\s*(\d+)\s*(?:Yrs?|Y)\s*/\s*(Male|Female|Other)'
    
    # Step 3: Extract the name
    match = re.search(name_pattern, text)
    if match:
        extracted_name = match.group(1)
    else:
        print('Name not found')
    
    age_gender_match = re.search(age_gender_pattern, text)
    if age_gender_match:
        extracted_age = age_gender_match.group(1).strip()  # Extracting the age
        extracted_gender = age_gender_match.group(2).strip()  # Extracting the gender
    else:
        print('Age/Gender not found')
    
    patient_details = {
        "Patient Details": [
            {
                "Patient Name": extracted_name,
                "Age": extracted_age,
                "Gender": extracted_gender
            }
        ]
    }
    
    return patient_details

def extract_test_results(text, test_names):
    results = []

    # Create a regex pattern to match any word starting with the specified test names
    pattern_parts = [re.escape(name).replace('\\ ', r'\s*') for name in test_names]
    result_pattern = (
        r'(\b(?:' + '|'.join(pattern_parts) + r')[^\n:,-]*?)'  # Match test name
        r'[:\-]?\s*'  # Match colon or hyphen followed by optional spaces
        r'(\d+\.?\d*)\s*'  # Match result (numeric value)
        r'((ng/mL|pg/mL|mg/dL|Ratio|U/L|gm/dL|μg/dL|μIU/mL|mmol/L|%|Laks\s*/?\s*cumm|cumm|mill/cumm)\b)?'  # Capture specific units
    )

    # Search the text using the regex pattern
    matches = re.findall(result_pattern, text, flags=re.IGNORECASE | re.DOTALL)

    # For each matched result, find the corresponding test name in test_names
    for match in matches:
        matched_test_name = match[0].strip()  # Extract the test name from the text
        result = match[1].strip()  # Extract the result
        matched_unit = match[2].strip() if match[2] else None  # Extract the unit if present

        # Find the original test name from test_names that corresponds to the match
        original_test_name = next((name for name in test_names if re.search(re.escape(name), matched_test_name, re.IGNORECASE)), matched_test_name)

        # Assign the unit: if matched unit is None or empty, use the default from default_units
        unit = matched_unit if matched_unit else default_units.get(original_test_name, 'N/A')

        # Append the original test name, result, and unit to the results list
        results.append({
            "Test Name": original_test_name,  # Use the original test name
            "Result": result,
            "Unit": unit  # Use the matched unit or default if not found
        })

    return results

import argparse
import pandas as pd
import re
import fitz  # PyMuPDF
import json
from pdfminer.high_level import extract_text

# Your existing functions...

def main(csv_file, pdf_file):
    # Step 1: Read test names from the CSV file
    test_names = read_test_names(csv_file)

    # Step 2: Extract text from the PDF file
    pdf_text = extract_text_from_pdf(pdf_file)

    # Clean the extracted text by removing unwanted patterns
    unwanted_pattern = r"(Sample\s*:\s*.*?\n)?(Method\s*:\s*.*?\n)?"
    cleaned_text = re.sub(unwanted_pattern, "", pdf_text, flags=re.DOTALL)

    # Step 3: Extract test results based on the test names
    extracted_results = extract_test_results(cleaned_text, test_names)

    # Step 4: Extract demographic information from the PDF file
    patient_details = extract_demography_from_pdf(pdf_file)

    # Combine patient details with extracted results
    final_json = patient_details
    final_json["Test Results"] = extracted_results

    # Convert to JSON string for output
    json_output = json.dumps(final_json, indent=4)
    print(json_output)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Extract test results and patient demographics from a PDF.")
    parser.add_argument("--csv_file", required=True, help="Path to the CSV file containing test names.")
    parser.add_argument("--pdf_file", required=True, help="Path to the PDF file containing patient data.")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the main function with the provided arguments
    main(args.csv_file, args.pdf_file)
