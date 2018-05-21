import numpy as np
import tensorflow as tf

def bbox_transform(ex_rois, gt_rois):
    ex_widths = ex_rois[:, 3]
    ex_heights = ex_rois[:, 2]
    ex_ctr_x = ex_rois[:, 0]
    ex_ctr_y = ex_rois[:, 1]

    gt_widths = gt_rois[:, 3]
    gt_heights = gt_rois[:, 2]
    gt_ctr_x = gt_rois[:, 0]
    gt_ctr_y = gt_rois[:, 1]

    targets_dx = (gt_ctr_x - ex_ctr_x) / ex_widths
    targets_dy = (gt_ctr_y - ex_ctr_y) / ex_heights
    targets_dw = np.log(gt_widths / ex_widths)
    targets_dh = np.log(gt_heights / ex_heights)

    targets = np.vstack(
        (targets_dx, targets_dy, targets_dw, targets_dh)).transpose()
    return targets

def bbox_transform_inv_tf(boxes, deltas):
    boxes = tf.cast(boxes, deltas.dtype)
    widths = tf.subtract(boxes[:, 2], boxes[:, 0]) + 1.0
    heights = tf.subtract(boxes[:, 3], boxes[:, 1]) + 1.0
    ctr_x = tf.add(boxes[:, 0], widths * 0.5)
    ctr_y = tf.add(boxes[:, 1], heights * 0.5)

    dx = deltas[:, 0]
    dy = deltas[:, 1]
    dw = deltas[:, 2]
    dh = deltas[:, 3]

    pred_ctr_x = tf.add(tf.multiply(dx, widths), ctr_x)
    pred_ctr_y = tf.add(tf.multiply(dy, heights), ctr_y)
    pred_w = tf.multiply(tf.exp(dw), widths)
    pred_h = tf.multiply(tf.exp(dh), heights)

    pred_boxes0 = tf.subtract(pred_ctr_x, pred_w * 0.5)
    pred_boxes1 = tf.subtract(pred_ctr_y, pred_h * 0.5)
    pred_boxes2 = tf.add(pred_ctr_x, pred_w * 0.5)
    pred_boxes3 = tf.add(pred_ctr_y, pred_h * 0.5)

    return tf.stack([pred_boxes0, pred_boxes1, pred_boxes2, pred_boxes3], axis=1)

def clip_boxes_tf(boxes, im_info):
    x_center = boxes[:, 0]
    y_center = boxes[:, 1]
    h = boxes[:, 2]
    w = boxes[:, 3]
    angle = boxes[:, 4]

    sin_abs = tf.abs(tf.sin(angle))
    cos_abs = tf.abs(tf.cos(angle))
    y_top = y_center + (w * sin_abs + h * cos_abs) / 2
    y_bot = y_center - (w * sin_abs + h * cos_abs) / 2
    x_top = x_center + (w * cos_abs + h * sin_abs) / 2
    x_bot = x_center - (w * cos_abs + h * sin_abs) / 2

    x_bot = tf.maximum(x_bot, 0)
    y_bot = tf.maximum(y_bot, 0)
    x_top = tf.minimum(x_top, im_info[1] - 1)
    y_top = tf.minimum(y_top, im_info[0] - 1)

    h_new = (tf.multiply(cos_abs, y_top - y_bot) - tf.multiply(sin_abs, x_top - x_bot)) / (tf.pow(cos_abs, 2) - tf.pow(sin_abs, 2))
    w_new = tf.multiply(w, h_new) / h

    return tf.stack([x_center, y_center, h_new, w_new, angle], axis=1)

def clockwise_sort(points):
    if len(points) == 3:
        return points

    l = np.argmin(points[:, 0])
    p_flag = points[l]
    above = np.array([p for p in points if p[1] >= p_flag[1]])
    below = np.array([p for p in points if p[1] < p_flag[1]])
    above = above[above[:, 0].argsort()]
    below = below[below[:, 0].argsort()[::-1]]
    points = np.concatenate((above, below))
    return points

def bbox_overlaps(boxes, query_boxes):
    N = boxes.shape[0]
    K = query_boxes.shape[0]
    overlaps = np.reshape(np.zeros((N, K)), (N,K))
    delta_theta = np.reshape(np.zeros((N, K)), (N,K))

    for k in range(K):
        rect1 = ((query_boxes[k][0], query_boxes[k][1]),
                 (query_boxes[k][2], query_boxes[k][3]),
                 query_boxes[k][5])
        for n in range(N):
            rect2 = ((boxes[n][0], boxes[n][1]),
                     (boxes[n][2], boxes[n][3]),
                     boxes[n][5])
            num_int, points = cv2.rotatedRectangleIntersection(rect1, rect2)
            S1 = query_boxes[k][2] * query_boxes[k][3]
            S2 = boxes[n][2] * boxes[n][3]
            if num_int == 1 and len(points) > 2:
                points = clockwise_sort(points)
                s = cv2.contourArea(points)
                overlaps[n][k] = s / (S1 + S2 - s)
            elif num_int == 2:
                overlaps[n][k] = min(S1, S2) / max(S1, S2)
            delta_theta[n][k] = np.abs(query_boxes[k][5] - boxes[n][5])
    return overlaps, delta_theta
