import cv2
import math
import numpy as np

def order_points(pts):
	"""
	Sắp xếp 4 điểm theo thứ tự:
	top-left, top-right, bottom-right, bottom-left
	"""
	pts = np.array(pts, dtype="float32")
	rect = np.zeros((4, 2), dtype="float32")

	s = pts.sum(axis=1)
	rect[0] = pts[np.argmin(s)]   # top-left
	rect[2] = pts[np.argmax(s)]   # bottom-right

	diff = np.diff(pts, axis=1)
	rect[1] = pts[np.argmin(diff)]  # top-right
	rect[3] = pts[np.argmax(diff)]  # bottom-left

	return rect

def four_point_transform(image, pts):
	"""
	Biến đổi phối cảnh ảnh dựa trên 4 điểm.
	"""
	rect = order_points(pts)
	(tl, tr, br, bl) = rect

	width_a = np.linalg.norm(br - bl)
	width_b = np.linalg.norm(tr - tl)
	max_width = int(max(width_a, width_b))

	height_a = np.linalg.norm(tr - br)
	height_b = np.linalg.norm(tl - bl)
	max_height = int(max(height_a, height_b))

	# Tránh ảnh quá nhỏ
	max_width = max(max_width, 1)
	max_height = max(max_height, 1)

	dst = np.array([
		[0, 0],
		[max_width - 1, 0],
		[max_width - 1, max_height - 1],
		[0, max_height - 1]
	], dtype="float32")

	M = cv2.getPerspectiveTransform(rect, dst)
	warped = cv2.warpPerspective(image, M, (max_width, max_height))
	return warped

def deskew_license_plate(plate_img, points, o):
	if plate_img is None or plate_img.size == 0:
		raise ValueError("plate_img rỗng hoặc không hợp lệ")

	pts = get_rel_4_points(points, o)

	img = plate_img.copy()

	warped = four_point_transform(img, pts)
	return warped


CLASSES = ['1', '2', '3', '4', '5', '6', '7', '8', '9',
		   'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
		   'K', 'L', 'M', 'N',
		   'P', 'S', 'T', 'U', 'V',
		   'X', 'Y', 'Z',
		   '0']

def read_plate(yolo_license_plate, im):
    LP_type = "1"
    results = yolo_license_plate(im, verbose=False)
    bb_list = results[0].boxes.xyxy.tolist()
    char_list = list(map(int, results[0].boxes.cls.tolist()))
    
    if len(bb_list) < 3:
        return "", 0.0

    conf = results[0].boxes.conf.mean().item()

    center_list = []
    for i, bb in enumerate(bb_list):
        x_c = (bb[0]+bb[2])/2
        y_c = (bb[1]+bb[3])/2
        center_list.append([x_c, y_c, CLASSES[char_list[i]]])

    # Sắp xếp các ký tự theo tọa độ Y để tìm khoảng cách lớn nhất giữa các dòng
    y_sorted = sorted(center_list, key=lambda x: x[1])
    y_coords = [c[1] for c in y_sorted]
    
    # Tính khoảng cách Y giữa các ký tự liên tiếp
    y_diffs = np.diff(y_coords)
    if len(y_diffs) > 0:
        max_diff_idx = np.argmax(y_diffs)
        max_diff = y_diffs[max_diff_idx]
        
        avg_char_height = np.mean([bb[3]-bb[1] for bb in bb_list])
        if max_diff > avg_char_height * 0.5:
            LP_type = "2"
            y_split = (y_coords[max_diff_idx] + y_coords[max_diff_idx+1]) / 2

    license_plate = ""
    if LP_type == "2":
        line_1 = [c for c in center_list if c[1] < y_split]
        line_2 = [c for c in center_list if c[1] >= y_split]
        
        for l1 in sorted(line_1, key=lambda x: x[0]):
            license_plate += str(l1[2])
        license_plate += " "
        for l2 in sorted(line_2, key=lambda x: x[0]):
            license_plate += str(l2[2])
    else:
        for l in sorted(center_list, key=lambda x: x[0]):
            license_plate += str(l[2])
            
    return license_plate, conf


def order_points_clockwise(pts):
    pts = np.asarray(pts, dtype=np.float32)
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
    return pts[np.argsort(angles)]

def find_quadrilateral_vertices(points):
    pts = np.asarray(points, dtype=np.float32)

    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("points phải có shape (n, 2)")
    if len(pts) < 4:
        raise ValueError("Cần ít nhất 4 điểm")

    # 1) Bao lồi
    hull = cv2.convexHull(pts)  # shape: (m, 1, 2)
    peri = cv2.arcLength(hull, True)

    # 2) Tìm epsilon phù hợp để approx về 4 đỉnh
    best = None
    best_diff = float("inf")

    for ratio in np.linspace(0.001, 0.2, 200):
        approx = cv2.approxPolyDP(hull, ratio * peri, True)
        m = len(approx)

        if m == 4:
            quad = approx.reshape(-1, 2)
            return order_points_clockwise(quad)

        diff = abs(m - 4)
        if diff < best_diff:
            best_diff = diff
            best = approx

    # 3) Nếu không ra đúng 4 đỉnh thì trả về gần nhất
    quad = best.reshape(-1, 2)
    if len(quad) > 4:
        quad = quad[:4]
    return order_points_clockwise(quad)

def get_rel_4_points(src, o):
	dst = []
	for x, y in src:
		new_x = x - o[0]
		new_y = y - o[1]
		dst.append((new_x, new_y))
	return np.array(dst)
