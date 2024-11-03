##Library imports
import os
import pytesseract
from PIL import Image
import cv2
from matplotlib import pyplot as plt
import re
from pdf2image import convert_from_path
import pandas as pd
import json
import glob
import argparse

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

## Convert PDF to images
def conver_pdf_to_image(pdf_file):
    images = convert_from_path(pdf_file, dpi=300)  # Higher DPI for better quality
    for i, img in enumerate(images):
        # Resize and crop image to resemble a phone screenshot
        img_resized = img.resize((1080, 1920), Image.LANCZOS)
        # Save as JPG
        img_resized.save(f'img/page_{i+1}.jpg', 'JPEG', quality=90)


def extract_demography_from_pdf(img):
    text = pytesseract.image_to_string(img)
    #print(text)
    # Step 2: Define regex pattern for Name
    # This pattern accounts for optional titles (Mr., Ms., etc.) and handles tabs and spaces
    name_pattern = r"(?i)NAME\.?\s*[:\t]*\s*(?:Mr\.|Ms\.|Mrs\.|Dr\.|COL\.)?\s*([A-Za-z\s]+)"
    extracted_name = ''
    # Step 3: Extract the name
    match = re.search(name_pattern, text)
    if match:
        extracted_name = match.group(1)
    else:
        print('Name not found')
        
    unwanted_patterns = [
        r"(?i)Billing Date\s*",
        r"(?i)OP Reg No\s*",
        r"(?i)Age\s*",
        r"(?i)Lab No\s*",
        r"(?i)UHID NOWVisit ID\s*"
        ]
    count = 0
    # Remove all unwanted patterns by looping through the list
    for pattern in unwanted_patterns:
        if (count==0):
            cleaned_text = re.sub(pattern, "", extracted_name, flags=re.DOTALL)
        else:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.DOTALL)
        count+=1
    
    patient_details = {
        "Patient Details": [
            {
                "Patient Name": cleaned_text
            }
        ]
    }
    
    return patient_details

# Read test names from CSV
def read_test_names(csv_file):
    df = pd.read_csv(csv_file)
    return df['Test_Name'].tolist()  # Adjust the column name as necessary

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

# Your existing functions...

def main(csv_file, pdf_file):
    folder_path = 'img/'
    bool_val = conver_pdf_to_image(pdf_file)
    # List only .jpg files and extract page numbers
    jpg_files = [f for f in os.listdir(folder_path) if f.endswith('.jpg') and os.path.isfile(os.path.join(folder_path, f))]
    test_names = read_test_names(csv_file)
    final_result = []
    jpg_files_sorted = sorted(jpg_files, key=lambda x: int(re.search(r'(\d+)', x).group()))
    data=[]
    counter = 0 
    for i in jpg_files_sorted:
        img  = cv2.imread(f'img/{i}')
        # Step 2: Extract text from PDF
        text = pytesseract.image_to_string(img)
        unwanted_patterns = [
            r"(Sample\s*:\s*.*?\n)?(Method\s*:\s*.*?\n)?",
            r"Ref\. Cust : PHLB_\d+ ?"
            ]
        count = 0
        # Remove all unwanted patterns by looping through the list
        for pattern in unwanted_patterns:
            if (count==0):
                cleaned_text = re.sub(pattern, "", text, flags=re.DOTALL)
            else:
                cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.DOTALL)
            count+=1
        #extract name
        if counter == 0 :
            patient_details = extract_demography_from_pdf(img)
            counter += 1
        
        # Step 3: Extract results based on test names
        extracted_results = extract_test_results(cleaned_text, test_names)
        # Process each item in extracted_results
        output_json = json.dumps(extracted_results)
        final_result += extracted_results
    
    # Output in JSON format
    output_json = json.dumps(final_result, indent=4)
    patient_json = patient_details
    patient_json["Test Results"] = final_result
    json_output = json.dumps(patient_json, indent=4)
    print(json_output)

    folder_path = 'img/'
    files = glob.glob(f"{folder_path}/*")
    for file in files:
        if os.path.isfile(file):
            os.remove(file)  # Delete each file
    print("All files have been deleted.")


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Extract test results and patient demographics from a PDF.")
    parser.add_argument("--csv_file", required=True, help="Path to the CSV file containing test names.")
    parser.add_argument("--pdf_file", required=True, help="Path to the PDF file containing patient data.")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the main function with the provided arguments
    main(args.csv_file, args.pdf_file)
