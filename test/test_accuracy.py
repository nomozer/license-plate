import os
import sys
import glob
import cv2
import csv
import re
import shutil
import patoolib

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, parent_dir)
os.chdir(parent_dir)

from lpAppModel import LPAppModel


def extract_archive(archive_path, extract_to):
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)
    os.makedirs(extract_to)
    patoolib.extract_archive(archive_path, outdir=extract_to, interactive=False)


def run_test(target_path, output_csv):
    is_archive = os.path.isfile(target_path) and target_path.lower().endswith(('.rar', '.zip'))
    extract_dir = os.path.join(current_dir, "temp_extracted_imgs")

    if is_archive:
        extract_archive(target_path, extract_dir)
        folder_path = extract_dir
    else:
        folder_path = target_path

    model = LPAppModel()

    image_paths = sorted(set(
        p
        for ext in ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.JPG', '*.JPEG', '*.PNG', '*.BMP')
        for p in glob.glob(os.path.join(folder_path, '**', ext), recursive=True)
    ))

    if not image_paths:
        print("Không tìm thấy ảnh nào!")
        if is_archive:
            shutil.rmtree(extract_dir)
        return

    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Filename', 'Biensoxe'])

        for idx, path in enumerate(image_paths):
            img_name = os.path.basename(path)
            img = cv2.imread(path)
            if img is None:
                continue

            print(f"[{idx+1}/{len(image_paths)}] {img_name}")
            model.detect_n_read(img)

            plates = [
                re.sub(r'[^A-Za-z0-9]', '', t).upper()
                for t in model.lp_texts if t
            ]
            writer.writerow([img_name, "||".join(filter(None, plates))])

    print(f"Xong! => {output_csv}")

    if is_archive and os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)


if __name__ == "__main__":
    target = os.path.join(parent_dir, 'sumdoc.rar')
    output_csv = os.path.join(current_dir, 'report.csv')
    run_test(target, output_csv)
