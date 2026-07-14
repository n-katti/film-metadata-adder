import exiftool
from pathlib import Path
from datetime import datetime
import shutil


# SET THESE VARIABLES
camera_make = "Canon"
camera_model = "Sure Shot 80u"
film_stock = "Fujifilm 400"
film_format = "35mm"

# Variables for the roll folder and roll number
roll_folder = Path("rolls/")
roll_folder.mkdir(exist_ok=True)
roll_number = "01"

# Roll path variables
roll_path = Path(roll_folder) / f"roll_{roll_number}.txt"

# Scan JPG path variables
scan_path = Path("scans/")
scan_path.mkdir(exist_ok=True)

# Output path variables
output_path = Path("output/")
output_path.mkdir(exist_ok=True)

# Log variables
log_path = Path("logs")
log_path.mkdir(exist_ok=True)
report_path = Path("logs") / f"roll_{roll_number}_verification.txt"
verification_results = []




# Imports metadata from the film log file and returns a list of dictionaries
def import_metadata_file():
    film_log_data = []

    with open(roll_path, "r") as file:
        content = file.read()
        film_data = content.splitlines()

        # Get a list of column names from the first line of the film log file
        columns = [x.strip().lower() for x in film_data[0].split("|")]

        # Iterate through the remaining lines of the film log file and create a dictionary for each entry
        for line in film_data[1:]:
            log_entry = [x.strip() for x in line.split("|")]
            log_entry = dict(zip(columns, log_entry))
            film_log_data.append(log_entry)
    return film_log_data

# Imports scans from the scans folder and returns a sorted list of scan files
def import_scans():
    scans = [f for f in scan_path.iterdir() if f.is_file()]
    scans.sort()
    return scans

# Validates that the number of entries in the film log matches the number of scans
def validate_data(film_log_data, scans):
    if len(film_log_data) == len(scans):
        print(f"✓ Passed: {len(film_log_data)} entries in the film log and {len(scans)} scans found.")
    else:
        raise ValueError(f"✗ Failed: {len(film_log_data)} entries in the film log and {len(scans)} scans found.")

# Combines the film log data with the corresponding scan files and returns a list of dictionaries
def normalize_metadata(film_log_data, scans):
    normalized_metadata = []

    for frame_number, (entry, scan) in enumerate(zip(film_log_data, scans), start=1):
        normalized_metadata.append({
            "original_file": scan,
            "output_file": None,

            "roll_number": roll_number,
            "film_stock": film_stock,
            "film_format": film_format,

            "frame_number": frame_number,

            "timestamp": datetime.fromisoformat(entry["timestamp"]),
            "latitude": float(entry["latitude"]),
            "longitude": float(entry["longitude"]),

            "camera_make": camera_make,
            "camera_model": camera_model,

            "description": entry["description"],
        })

    return normalized_metadata

def generate_exif_metadata(frame):
    timestamp = frame["timestamp"]

    latitude = frame["latitude"]
    longitude = frame["longitude"]

    # Determine GPS hemisphere references
    latitude_ref = "N" if latitude >= 0 else "S"
    longitude_ref = "E" if longitude >= 0 else "W"

    exif_metadata = {
        "EXIF:DateTimeOriginal": timestamp.strftime("%Y:%m:%d %H:%M:%S"),
        "EXIF:CreateDate": timestamp.strftime("%Y:%m:%d %H:%M:%S"),
        "EXIF:ModifyDate": timestamp.strftime("%Y:%m:%d %H:%M:%S"),
        "EXIF:OffsetTimeOriginal": timestamp.strftime("%z")[:3] + ":" + timestamp.strftime("%z")[3:],

        "EXIF:GPSLatitude": abs(latitude),
        "EXIF:GPSLatitudeRef": latitude_ref,
        "EXIF:GPSLongitude": abs(longitude),
        "EXIF:GPSLongitudeRef": longitude_ref,

        "EXIF:Make": frame["camera_make"],
        "EXIF:Model": frame["camera_model"],

        "EXIF:ImageDescription": frame["description"],
        
        "XMP-dc:Title": (
            f"Roll {frame['roll_number']} "
            f"Frame {frame['frame_number']}"
        ),

        "XMP-dc:Subject": [
            f"{frame['film_stock']} {frame['film_format']}"
        ],
    }   

    return exif_metadata

def create_output_file(frame):

    original = frame["original_file"]

    output_file = output_path / original.name

    shutil.copy2(original, output_file)

    frame["output_file"] = output_file

    return frame

def write_exif(frame):
    exif_data = generate_exif_metadata(frame)

    with exiftool.ExifToolHelper() as et:
        print(exif_data)
        et.set_tags(
            [str(frame["output_file"])],
            exif_data,
            params=["-overwrite_original"]
        )
    print("EXIF metadata written to", frame["output_file"])

def verify_exif(frame):
    expected = generate_exif_metadata(frame)

    with exiftool.ExifToolHelper() as et:
        actual = et.get_metadata([str(frame["output_file"])])[0]

    checks = {
        "DateTimeOriginal": (
            expected["EXIF:DateTimeOriginal"],
            actual.get("EXIF:DateTimeOriginal")
        ),
        "OffsetTimeOriginal": (
            expected["EXIF:OffsetTimeOriginal"],
            actual.get("EXIF:OffsetTimeOriginal")
        ),
        "GPS Latitude": (
            expected["EXIF:GPSLatitude"],
            actual.get("EXIF:GPSLatitude")
        ),
        "GPS Latitude Ref": (
            expected["EXIF:GPSLatitudeRef"],
            actual.get("EXIF:GPSLatitudeRef")
        ),
        "GPS Longitude": (
            expected["EXIF:GPSLongitude"],
            actual.get("EXIF:GPSLongitude")
        ),
        "GPS Longitude Ref": (
            expected["EXIF:GPSLongitudeRef"],
            actual.get("EXIF:GPSLongitudeRef")
        ),
        "Camera Make": (
            expected["EXIF:Make"],
            actual.get("EXIF:Make")
        ),
        "Camera Model": (
            expected["EXIF:Model"],
            actual.get("EXIF:Model")
        ),
        "Description": (
            expected["EXIF:ImageDescription"],
            actual.get("EXIF:ImageDescription")
        ),
        "XMP Title": (
            expected["XMP-dc:Title"],
            actual.get("XMP:Title")
        ),
        "XMP Subject": (
            expected["XMP-dc:Subject"][0],
            actual.get("XMP:Subject")
        ),
    }

    failures = []

    for name, (expected_value, actual_value) in checks.items():
        if expected_value != actual_value:
            failures.append({
                "field": name,
                "expected": expected_value,
                "actual": actual_value
            })

    return {
        "file": frame["output_file"].name,
        "passed": len(failures) == 0,
        "failures": failures
    }

def generate_report(results):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    with open(report_path, "w", encoding="utf-8") as file:
        file.write("Film Metadata Verification Report\n")
        file.write("=" * 35 + "\n\n")

        file.write(f"Generated: {datetime.now()}\n")
        file.write(f"Roll: {roll_number}\n")
        file.write(f"Camera: {camera_make} {camera_model}\n")
        file.write(f"Film: {film_stock} {film_format}\n\n")

        file.write("Summary\n")
        file.write("-" * 35 + "\n")
        file.write(f"Total frames processed: {total}\n")
        file.write(f"Passed: {passed}\n")
        file.write(f"Failed: {failed}\n\n")

        if failed:
            file.write("Failures\n")
            file.write("-" * 35 + "\n\n")

            for result in results:
                if not result["passed"]:
                    file.write(f"{result['file']}\n")
                    file.write("-" * len(result["file"]) + "\n")

                    for failure in result["failures"]:
                        file.write(f"✗ {failure['field']}\n")
                        file.write(f"  Expected: {failure['expected']}\n")
                        file.write(f"  Actual:   {failure['actual']}\n\n")

        else:
            file.write("All frames passed verification.\n")

    print(f"\nVerification report written to {report_path}")

metadata = import_metadata_file()
scans = import_scans()
validate_data(metadata, scans)

normalized = normalize_metadata(
    film_log_data=metadata,
    scans=scans
)

for frame in normalized:
    create_output_file(frame)
    write_exif(frame)

    result = verify_exif(frame)
    verification_results.append(result)


generate_report(verification_results)






