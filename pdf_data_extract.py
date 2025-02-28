import os
import re
import json
import glob
import argparse
import pandas as pd
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import cv2

# Default units for test results
DEFAULT_UNITS = {
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
}


def convert_pdf_to_images(pdf_file, output_folder='img/', dpi=300):
    images = convert_from_path(pdf_file, dpi=dpi)
    for index, image in enumerate(images):
        resized_image = image.resize((1080, 1920), Image.LANCZOS)
        resized_image.save(os.path.join(output_folder, f'page_{index + 1}.jpg'), 'JPEG', quality=90)


def extract_patient_name_from_image(image):
    text = pytesseract.image_to_string(image)

    name_pattern = r"(?i)NAME\.?\s*[:\t]*\s*(?:Mr\.|Ms\.|Mrs\.|Dr\.|COL\.)?\s*([A-Za-z\s]+)"
    match = re.search(name_pattern, text)

    extracted_name = match.group(1) if match else None

    if not extracted_name:
        print("Patient name not found.")
        return {"Patient Name": "Unknown"}

    unwanted_patterns = [
        r"(?i)Billing Date\s*",
        r"(?i)OP Reg No\s*",
        r"(?i)Age\s*",
        r"(?i)Lab No\s*",
        r"(?i)UHID NOWVisit ID\s*"
    ]
    
    for pattern in unwanted_patterns:
        extracted_name = re.sub(pattern, "", extracted_name, flags=re.DOTALL)

    return {"Patient Name": extracted_name.strip()}


def read_test_names_from_csv(csv_file):
    df = pd.read_csv(csv_file)
    return df['Test_Name'].tolist()


def extract_test_results(text, test_names):
    results = []
    pattern_parts = [re.escape(name).replace('\\ ', r'\s*') for name in test_names]

    result_pattern = (
        r'(\b(?:' + '|'.join(pattern_parts) + r')[^\n:,-]*?)'
        r'[:\-]?\s*'
        r'(\d+\.?\d*)\s*'
        r'((ng/mL|pg/mL|mg/dL|Ratio|U/L|gm/dL|μg/dL|μIU/mL|mmol/L|%|Laks\s*/?\s*cumm|cumm|mill/cumm)\b)?'
    )

    matches = re.findall(result_pattern, text, flags=re.IGNORECASE | re.DOTALL)

    for match in matches:
        matched_name, result, matched_unit = match
        matched_name = matched_name.strip()
        result = result.strip()
        matched_unit = matched_unit.strip() if matched_unit else None

        original_name = next((name for name in test_names if re.search(re.escape(name), matched_name, re.IGNORECASE)), matched_name)

        unit = matched_unit or DEFAULT_UNITS.get(original_name, 'N/A')

        results.append({
            "Test Name": original_name,
            "Result": result,
            "Unit": unit
        })

    return results


def clean_text(text):
    unwanted_patterns = [
        r"(Sample\s*:\s*.*?\n)?(Method\s*:\s*.*?\n)?",
        r"Ref\. Cust : PHLB_\d+ ?"
    ]
    cleaned_text = text
    for pattern in unwanted_patterns:
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.DOTALL)
    return cleaned_text


def delete_folder_contents(folder_path):
    files = glob.glob(f"{folder_path}/*")
    for file in files:
        if os.path.isfile(file):
            os.remove(file)
    print(f"All files in {folder_path} have been deleted.")


def process_pdf(csv_file, pdf_file):
    output_folder = 'img'
    convert_pdf_to_images(pdf_file, output_folder)

    image_files = sorted(
        [f for f in os.listdir(output_folder) if f.endswith('.jpg')],
        key=lambda x: int(re.search(r'(\d+)', x).group())
    )

    test_names = read_test_names_from_csv(csv_file)
    all_results = []

    patient_details = None

    for index, file_name in enumerate(image_files):
        image_path = os.path.join(output_folder, file_name)
        image = cv2.imread(image_path)

        text = pytesseract.image_to_string(image)
        cleaned_text = clean_text(text)

        if index == 0:
            patient_details = extract_patient_name_from_image(image)

        extracted_results = extract_test_results(cleaned_text, test_names)
        all_results.extend(extracted_results)

    if patient_details is None:
        patient_details = {"Patient Name": "Unknown"}

    output_data = {
        "Patient Details": [patient_details],
        "Test Results": all_results
    }

    print(json.dumps(output_data, indent=4))

    delete_folder_contents(output_folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract test results and patient information from a PDF report.")
    parser.add_argument("--csv_file", required=True, help="Path to the CSV file containing test names.")
    parser.add_argument("--pdf_file", required=True, help="Path to the PDF file containing patient data.")

    args = parser.parse_args()
    process_pdf(args.csv_file, args.pdf_file)
