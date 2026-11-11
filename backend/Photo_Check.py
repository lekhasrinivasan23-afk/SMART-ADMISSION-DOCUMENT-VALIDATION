import os
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


def validate_photo(image_path):

    result = {
        "status": "REVIEW",
        "message": "",
        "file_name": os.path.basename(str(image_path)),
        "file_size_kb": 0,
        "width": 0,
        "height": 0,
        "format": "",
        "brightness": 0,
        "blur_score": 0
    }

    try:
        # Check whether file exists
        if not os.path.isfile(image_path):
            result["status"] = "FAIL"
            result["message"] = "Photo file not found."
            return result

        # Check file size
        file_size = os.path.getsize(image_path)
        result["file_size_kb"] = round(file_size / 1024, 2)

        if file_size == 0:
            result["status"] = "FAIL"
            result["message"] = "Photo file is empty."
            return result

        if file_size > 5 * 1024 * 1024:
            result["status"] = "FAIL"
            result["message"] = "Photo size exceeds 5 MB."
            return result

        # Open and validate image
        with Image.open(image_path) as img:

            result["format"] = img.format

            if img.format not in ["JPEG", "PNG"]:
                result["status"] = "FAIL"
                result["message"] = "Only JPG and PNG formats are allowed."
                return result

            img = ImageOps.exif_transpose(img)
            img.load()

            width, height = img.size

            result["width"] = width
            result["height"] = height

            if width < 300 or height < 300:
                result["status"] = "FAIL"
                result["message"] = "Image resolution must be at least 300 x 300."
                return result

            # Convert image to grayscale
            gray = np.array(img.convert("L"))

            # Check brightness
            brightness = float(np.mean(gray))
            result["brightness"] = round(brightness, 2)

            # Check image sharpness
            blur_score = cv2.Laplacian(
                gray, cv2.CV_64F
            ).var()

            result["blur_score"] = round(float(blur_score), 2)

            # Quality review
            issues = []

            if brightness < 50:
                issues.append("Photo is too dark.")

            elif brightness > 220:
                issues.append("Photo is too bright.")

            if blur_score < 100:
                issues.append("Photo may be blurry.")

            if issues:
                result["status"] = "REVIEW"
                result["message"] = " ".join(issues)
            else:
                result["status"] = "PASS"
                result["message"] = "Photo validation successful."

            return result

    except (UnidentifiedImageError, OSError, ValueError):
        result["status"] = "FAIL"
        result["message"] = "Invalid or corrupted image file."
        return result

    except Exception as error:
        result["status"] = "REVIEW"
        result["message"] = f"Validation error: {error}"
        return result


if __name__ == "__main__":

    print("PHOTO VALIDATION MODULE")
    print("-----------------------")

    photo_path = input("Enter student photo path: ").strip().strip('"')

    validation = validate_photo(photo_path)

    print("\nVALIDATION RESULT")
    print("-----------------------")

    for key, value in validation.items():
        print(f"{key}: {value}") 
