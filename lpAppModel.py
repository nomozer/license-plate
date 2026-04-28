import os
import cv2
import numpy as np
from utilities import deskew_license_plate, read_plate, find_quadrilateral_vertices

from ultralytics import YOLO

MODEL_PATH = "best.pt"
OCR_MODEL_PATH = "ocr.pt"

class LPAppModel:
	def __init__(self):
		self.model = YOLO(MODEL_PATH)
		self.ocr = YOLO(OCR_MODEL_PATH)
		self.img = None
		self.detected_rects = []
		self.detected_masks = []
		self.detected_confs = []
		self.lp_imgs = []
		self.lp_texts = []
		self.lp_confs = []

	def _read_img(self, path):
		self.img = cv2.imread(path)

	def _detect_lp(self):
		self.detected_rects.clear()
		self.detected_confs.clear()
		self.detected_masks.clear()
		result = self.model(self.img, verbose=False)
		for box in result[0].boxes:
			x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
			conf = box.conf[0].item()
			self.detected_rects.append((x1, y1, x2, y2))
			self.detected_confs.append(conf)
		if result[0].masks:
			for mask in result[0].masks:
				self.detected_masks.append(find_quadrilateral_vertices(mask.xy[0]))
		else:
			self.detected_masks = self.detected_rects[:]

	def draw_rect(self, thickness=5):
		tmp = self.img.copy()
		for rect in self.detected_rects:
			x1, y1, x2, y2 = rect
			cv2.rectangle(tmp, (x1, y1), (x2, y2), (0, 255, 0), thickness)
		return tmp

	def _crop_lps(self):
		self.lp_imgs.clear()
		for x1, y1, x2, y2 in self.detected_rects:
			self.lp_imgs.append(self.img[y1:y2+1, x1:x2+1])

	def _deskew_lps(self):
		for i in range(len(self.lp_imgs)):
			o = (self.detected_rects[i][0], self.detected_rects[i][1])
			self.lp_imgs[i] = deskew_license_plate(self.lp_imgs[i], self.detected_masks[i], o)

	def _read_lp(self, lp_img):
		return read_plate(self.ocr, lp_img)

	def _read_lps(self):
		self.lp_texts.clear()
		self.lp_confs.clear()
		for _ in self.lp_imgs:
			text, conf = self._read_lp(_)
			self.lp_texts.append(text)
			self.lp_confs.append(conf)

	def detect_n_read(self, input_img):
		if isinstance(input_img, str):
			self._read_img(input_img)
		else:
			self.img = input_img
		self._detect_lp()
		self._crop_lps()
		self._deskew_lps()
		self._read_lps()
