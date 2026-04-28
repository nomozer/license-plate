import cv2
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
	max_width = max(int(max(width_a, width_b)), 1)

	height_a = np.linalg.norm(tr - br)
	height_b = np.linalg.norm(tl - bl)
	max_height = max(int(max(height_a, height_b)), 1)

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

	pts = np.array(points, dtype="float32") - np.array(o, dtype="float32")
	return four_point_transform(plate_img.copy(), pts)


CLASSES = ['1', '2', '3', '4', '5', '6', '7', '8', '9',
		   'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
		   'K', 'L', 'M', 'N',
		   'P', 'S', 'T', 'U', 'V',
		   'X', 'Y', 'Z',
		   '0']

CONF_THRESHOLD = 0.25

def read_plate(yolo_license_plate, im):
    results = yolo_license_plate(im, verbose=False)
    boxes = results[0].boxes
    bb_list = boxes.xyxy.tolist()
    confs = boxes.conf.tolist()
    char_list = list(map(int, boxes.cls.tolist()))

    # Lọc ký tự có confidence thấp (noise)
    filtered = [
        (bb, CLASSES[cls], c)
        for bb, cls, c in zip(bb_list, char_list, confs)
        if c >= CONF_THRESHOLD
    ]

    if len(filtered) < 3:
        return "", 0.0

    avg_conf = np.mean([f[2] for f in filtered])

    # Tính tâm mỗi ký tự
    center_list = [
        ((bb[0]+bb[2])/2, (bb[1]+bb[3])/2, char)
        for bb, char, _ in filtered
    ]

    # Phát hiện biển 1 dòng hay 2 dòng
    y_sorted = sorted(center_list, key=lambda c: c[1])
    y_coords = [c[1] for c in y_sorted]
    y_diffs = np.diff(y_coords)

    LP_type = "1"
    y_split = 0
    if len(y_diffs) > 0:
        max_diff_idx = np.argmax(y_diffs)
        avg_char_height = np.mean([bb[3]-bb[1] for bb, _, _ in filtered])
        if y_diffs[max_diff_idx] > avg_char_height * 0.5:
            LP_type = "2"
            y_split = (y_coords[max_diff_idx] + y_coords[max_diff_idx+1]) / 2

    # Ghép biển số
    if LP_type == "2":
        line_1 = sorted([c for c in center_list if c[1] < y_split], key=lambda x: x[0])
        line_2 = sorted([c for c in center_list if c[1] >= y_split], key=lambda x: x[0])
        license_plate = "".join(c[2] for c in line_1) + " " + "".join(c[2] for c in line_2)
    else:
        license_plate = "".join(c[2] for c in sorted(center_list, key=lambda x: x[0]))

    return license_plate, avg_conf


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

    hull = cv2.convexHull(pts)
    peri = cv2.arcLength(hull, True)

    # Binary search cho epsilon tối ưu thay vì brute-force 200 lần
    lo, hi = 0.001, 0.2
    best = None
    best_diff = float("inf")

    for _ in range(30):
        mid = (lo + hi) / 2
        approx = cv2.approxPolyDP(hull, mid * peri, True)
        m = len(approx)

        if m == 4:
            return order_points_clockwise(approx.reshape(-1, 2))

        diff = abs(m - 4)
        if diff < best_diff:
            best_diff = diff
            best = approx

        if m > 4:
            lo = mid
        else:
            hi = mid

    quad = best.reshape(-1, 2)
    if len(quad) > 4:
        quad = quad[:4]
    return order_points_clockwise(quad)
