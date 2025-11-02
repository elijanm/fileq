import cv2
import numpy as np
import requests
import json
import matplotlib.pyplot as plt
from scipy import ndimage

from skimage.segmentation import watershed
from scipy.signal import find_peaks

    
def count_maize_kernels(img, roi=None, imaging_mode='uv', environment='black_box',
                       kernel_size_range=(100, 3000), show_visualization=True):
    """
    Specialized maize kernel counting with techniques optimized for irregular, 
    densely packed kernels.
    
    Parameters:
        img: Input image
        roi: Region of interest (x, y, w, h)
        imaging_mode: 'uv' or 'white_light'
        environment: 'black_box' or 'open'
        kernel_size_range: (min_area, max_area) for individual kernels
        show_visualization: Whether to display results
    
    Returns:
        dict: Kernel count and analysis results
    """
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    is_uv = imaging_mode.lower() == 'uv'
    
    # Apply ROI
    if roi:
        x, y, w, h = roi
        x = max(0, min(x, gray.shape[1] - w))
        y = max(0, min(y, gray.shape[0] - h))
        w = min(w, gray.shape[1] - x)
        h = min(h, gray.shape[0] - y)
        gray_roi = gray[y:y+h, x:x+w]
        roi_offset = (x, y)
    else:
        gray_roi = gray
        roi_offset = (0, 0)
        x, y = 0, 0
    
    min_kernel_area, max_kernel_area = kernel_size_range
    
    # Enhanced preprocessing for maize kernels
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    
    # Contrast enhancement
    if is_uv and gray.mean() < 50:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(blurred)
    else:
        enhanced = blurred
    
    # Multiple segmentation approaches
    results_dict = {}
    
    # Method 1: Adaptive Threshold + Contour Analysis
    kernels_adaptive = count_by_adaptive_threshold(enhanced, min_kernel_area, max_kernel_area)
    results_dict['adaptive'] = kernels_adaptive
    
    # Method 2: Template Matching Approximation
    kernels_template = count_by_template_matching(enhanced, min_kernel_area, max_kernel_area)
    results_dict['template'] = kernels_template
    
    # Method 3: Enhanced Hough Circles (relaxed for irregular shapes)
    kernels_hough = count_by_flexible_hough(enhanced, min_kernel_area, max_kernel_area)
    results_dict['flexible_hough'] = kernels_hough
    
    # Method 4: Erosion-based separation
    kernels_erosion = count_by_erosion_separation(enhanced, min_kernel_area, max_kernel_area)
    results_dict['erosion'] = kernels_erosion
    
    # Method 5: Combined voting approach
    kernels_combined = combine_detection_methods(results_dict, enhanced.shape)
    
    # Use the combined result as primary
    valid_kernels = kernels_combined['contours']
    kernel_centers = kernels_combined['centers']
    kernel_areas = kernels_combined['areas']
    
    # Adjust centers for full image coordinates
    adjusted_centers = [(cx + roi_offset[0], cy + roi_offset[1]) for cx, cy in kernel_centers]
    
    # Calculate statistics
    kernel_count = len(valid_kernels)
    if kernel_count > 0:
        avg_area = np.mean(kernel_areas)
        std_area = np.std(kernel_areas)
        density = kernel_count / (gray_roi.shape[0] * gray_roi.shape[1]) * 10000
    else:
        avg_area = std_area = density = 0
    
    # Visualization
    if show_visualization:
        fig, axes = plt.subplots(2, 4, figsize=(20, 12))
        
        # Original image
        axes[0,0].imshow(gray, cmap='gray')
        axes[0,0].set_title('Original Image')
        if roi:
            rect = plt.Rectangle((x, y), w, h, linewidth=2, edgecolor='red', facecolor='none')
            axes[0,0].add_patch(rect)
        axes[0,0].axis('off')
        
        # Enhanced ROI
        axes[0,1].imshow(enhanced, cmap='gray')
        axes[0,1].set_title('Enhanced ROI')
        axes[0,1].axis('off')
        
        # Method comparison
        method_names = ['adaptive', 'template', 'flexible_hough', 'erosion']
        method_titles = ['Adaptive Thresh', 'Template Match', 'Flexible Hough', 'Erosion Sep']
        
        for i, (method, title) in enumerate(zip(method_names, method_titles)):
            if i < 2:
                ax = axes[0, i+2]
            else:
                ax = axes[1, i-2]
                
            method_result = results_dict[method]
            
            # Create visualization for this method
            method_img = np.zeros_like(enhanced)
            if method_result['contours']:
                cv2.fillPoly(method_img, method_result['contours'], 255)
            
            ax.imshow(method_img, cmap='gray')
            ax.set_title(f'{title}\n{len(method_result["contours"])} kernels')
            ax.axis('off')
        
        # Combined result
        axes[1,2].imshow(enhanced, cmap='gray')
        for i, (cx, cy) in enumerate(kernel_centers):
            axes[1,2].plot(cx, cy, 'r+', markersize=8, markeredgewidth=2)
            axes[1,2].text(cx+5, cy-5, str(i+1), color='yellow', fontsize=8, fontweight='bold')
        axes[1,2].set_title(f'Combined Result\n{kernel_count} kernels detected')
        axes[1,2].axis('off')
        
        # Statistics
        axes[1,3].axis('off')
        
        # Create method comparison
        method_counts = {name: len(results_dict[name]['contours']) for name in method_names}
        method_counts['combined'] = kernel_count
        
        stats_text = f"""MAIZE KERNEL COUNTING

METHOD COMPARISON:
• Adaptive Threshold: {method_counts['adaptive']}
• Template Matching: {method_counts['template']}
• Flexible Hough: {method_counts['flexible_hough']}
• Erosion Separation: {method_counts['erosion']}
• Combined Result: {method_counts['combined']}

KERNEL STATISTICS:
• Average Area: {avg_area:.0f} px²
• Area Std Dev: {std_area:.0f} px²
• Density: {density:.1f}/10k px²
• Size Range: {min_kernel_area}-{max_kernel_area} px²

IMAGING CONDITIONS:
• Mode: {imaging_mode.upper()}
• Environment: {environment.replace('_', ' ').title()}
• ROI: {roi if roi else 'Full image'}
"""
        
        axes[1,3].text(0.05, 0.95, stats_text, transform=axes[1,3].transAxes,
                      fontsize=10, verticalalignment='top', fontfamily='monospace',
                      bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        
        plt.tight_layout()
        plt.show()
    
    # Results
    results = {
        'kernel_count': kernel_count,
        'method_comparison': {name: len(results_dict[name]['contours']) for name in results_dict},
        'kernel_centers': adjusted_centers,
        'kernel_areas': kernel_areas,
        'average_area': avg_area,
        'area_std': std_area,
        'density_per_10k_pixels': density,
        'size_range_used': kernel_size_range,
        'roi_used': roi,
        'imaging_mode': imaging_mode,
        'environment': environment
    }
    
    return results


def count_by_adaptive_threshold(enhanced, min_area, max_area):
    """Count using adaptive thresholding with better filtering"""
    # More conservative adaptive threshold
    adaptive_thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY_INV, 15, 8)  # Smaller block, higher C
    
    # More aggressive morphological cleaning
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    
    # Remove small noise
    cleaned = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_OPEN, kernel_small, iterations=2)
    # Close gaps
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_medium, iterations=1)
    
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_contours = []
    centers = []
    areas = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            # Additional shape filtering for kernels
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                # More strict shape requirements
                circularity = 4 * np.pi * area / (perimeter ** 2)
                compactness = (perimeter ** 2) / (4 * np.pi * area)
                
                # Accept shapes that are somewhat compact and not too elongated
                if circularity > 0.15 and compactness < 4.0:
                    # Check aspect ratio
                    rect = cv2.minAreaRect(contour)
                    width, height = rect[1]
                    if width > 0 and height > 0:
                        aspect_ratio = max(width, height) / min(width, height)
                        if aspect_ratio < 3.0:  # Not too elongated
                            valid_contours.append(contour)
                            areas.append(area)
                            
                            M = cv2.moments(contour)
                            if M["m00"] != 0:
                                cx = int(M["m10"] / M["m00"])
                                cy = int(M["m01"] / M["m00"])
                            else:
                                cx, cy = 0, 0
                            centers.append((cx, cy))
    
    return {'contours': valid_contours, 'centers': centers, 'areas': areas}


def count_by_template_matching(enhanced, min_area, max_area):
    """Approximate template matching for kernel-like shapes"""
    # Use edge detection to find kernel boundaries
    edges = cv2.Canny(enhanced, 30, 80)
    
    # Dilate edges to create filled regions
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)
    
    # Fill holes
    contours_temp, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(dilated)
    cv2.fillPoly(filled, contours_temp, 255)
    
    contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_contours = []
    centers = []
    areas = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            # Additional shape filtering for kernel-like objects
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                compactness = (perimeter ** 2) / (4 * np.pi * area)
                if compactness < 3.0:  # Reasonably compact shape
                    valid_contours.append(contour)
                    areas.append(area)
                    
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = 0, 0
                    centers.append((cx, cy))
    
    return {'contours': valid_contours, 'centers': centers, 'areas': areas}


def count_by_flexible_hough(enhanced, min_area, max_area):
    """Modified Hough circles with relaxed parameters for irregular kernels"""
    min_radius = max(8, int(np.sqrt(min_area / np.pi) * 0.7))  # Smaller radius for irregular shapes
    max_radius = min(80, int(np.sqrt(max_area / np.pi) * 1.2))  # Larger radius tolerance
    
    all_circles = []
    
    # Multiple parameter sets for flexibility
    param_sets = [
        (40, 20, 8),   # Sensitive detection
        (50, 25, 12),  # Medium sensitivity
        (60, 30, 15),  # Conservative detection
    ]
    
    for param1, param2, min_dist in param_sets:
        circles = cv2.HoughCircles(enhanced, cv2.HOUGH_GRADIENT, 1, min_dist,
                                 param1=param1, param2=param2,
                                 minRadius=min_radius, maxRadius=max_radius)
        if circles is not None:
            all_circles.extend(circles[0])
    
    # Remove duplicates
    if all_circles:
        unique_circles = []
        for circle in all_circles:
            x, y, r = circle
            is_duplicate = False
            for existing in unique_circles:
                ex, ey, er = existing
                distance = np.sqrt((x-ex)**2 + (y-ey)**2)
                if distance < min(r, er) * 0.8:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_circles.append([int(x), int(y), int(r)])
        
        centers = [(x, y) for x, y, r in unique_circles]
        # Estimate areas from radii
        areas = [np.pi * r**2 for x, y, r in unique_circles]
        
        # Create contours from circles
        contours = []
        for x, y, r in unique_circles:
            # Create circular contour
            angles = np.linspace(0, 2*np.pi, 20)
            circle_points = np.array([[int(x + r*np.cos(angle)), int(y + r*np.sin(angle))] 
                                    for angle in angles])
            contours.append(circle_points.reshape((-1, 1, 2)))
        
        return {'contours': contours, 'centers': centers, 'areas': areas}
    
    return {'contours': [], 'centers': [], 'areas': []}


def count_by_erosion_separation(enhanced, min_area, max_area):
    """Use erosion to separate touching kernels"""
    # Threshold
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Morphological operations
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    
    # Clean up noise
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small, iterations=1)
    
    # Erode to separate touching objects
    eroded = cv2.erode(cleaned, kernel_large, iterations=2)
    
    # Find individual kernels
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_contours = []
    centers = []
    areas = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        # Use smaller area threshold since erosion reduces size
        if min_area * 0.3 <= area <= max_area * 0.8:
            valid_contours.append(contour)
            areas.append(area)
            
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = 0, 0
            centers.append((cx, cy))
    
    return {'contours': valid_contours, 'centers': centers, 'areas': areas}


def combine_detection_methods(results_dict, image_shape):
    """Combine results from multiple detection methods using voting"""
    h, w = image_shape
    
    # Create a voting map
    vote_map = np.zeros((h, w), dtype=np.float32)
    all_detections = []
    
    # Collect all center points with weights
    method_weights = {
        'adaptive': 0.6,        # Reduce weight due to over-segmentation
        'template': 1.0,        
        'flexible_hough': 1.8,  # Increase weight - this gave reasonable results
        'erosion': 1.2          # Moderate weight - conservative but reliable
    }
    
    for method_name, method_result in results_dict.items():
        weight = method_weights.get(method_name, 1.0)
        for i, (cx, cy) in enumerate(method_result['centers']):
            if 0 <= cx < w and 0 <= cy < h:
                # Add weighted vote in a small neighborhood
                cv2.circle(vote_map, (cx, cy), 15, weight, -1)
                all_detections.append({'x': cx, 'y': cy, 'method': method_name, 
                                     'area': method_result['areas'][i], 'weight': weight})
    
    # Find peaks in vote map with higher threshold to reduce false positives
    peak_threshold = vote_map.max() * 0.6  # Increased from 0.4 to be more selective
    _, peaks = cv2.threshold(vote_map, peak_threshold, 255, cv2.THRESH_BINARY)
    peaks = peaks.astype(np.uint8)
    
    contours, _ = cv2.findContours(peaks, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    combined_centers = []
    combined_areas = []
    combined_contours = []
    
    for contour in contours:
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Find the best area estimate from nearby detections
            nearby_areas = []
            for detection in all_detections:
                dist = np.sqrt((cx - detection['x'])**2 + (cy - detection['y'])**2)
                if dist < 20:  # Within neighborhood
                    nearby_areas.append(detection['area'])
            
            if nearby_areas:
                estimated_area = np.mean(nearby_areas)
                combined_centers.append((cx, cy))
                combined_areas.append(estimated_area)
                combined_contours.append(contour)
    
    return {'contours': combined_contours, 'centers': combined_centers, 'areas': combined_areas}



def diagnose_image_quality(img, roi=None, imaging_mode='uv', environment='black_box'):
    """
    Detailed diagnostics for image quality assessment with comprehensive visualizations.
    """
    if img is None:
        return "Image is None"
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    is_uv = imaging_mode.lower() == 'uv'
    is_black_box = environment.lower() == 'black_box'
    
    print(f"=== IMAGE DIAGNOSTICS ===")
    print(f"Imaging mode: {imaging_mode}")
    print(f"Environment: {environment}")
    print(f"Image shape: {gray.shape}")
    print(f"Image dtype: {gray.dtype}")
    print(f"Pixel value range: {gray.min()} - {gray.max()}")
    print(f"Mean pixel value: {gray.mean():.2f}")
    print(f"Std deviation: {gray.std():.2f}")
    
    # Create comprehensive visualization
    fig = plt.figure(figsize=(18, 14))
    
    # 1. Original grayscale image with ROI
    ax1 = plt.subplot(3, 4, 1)
    plt.imshow(gray, cmap='gray', aspect='equal')
    plt.title(f'Original Image\n{imaging_mode.upper()} - {environment.replace("_", " ").title()}')
    plt.colorbar(shrink=0.6)
    if roi:
        x, y, w, h = roi
        rect = plt.Rectangle((x, y), w, h, linewidth=2, edgecolor='red', facecolor='none')
        plt.gca().add_patch(rect)
        plt.text(x, y-10, 'ROI', color='red', fontweight='bold')
    plt.axis('off')
    
    # 2. Histogram analysis with environment-specific ranges
    ax2 = plt.subplot(3, 4, 2)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    hist_norm = hist / hist.sum()
    plt.plot(hist, color='blue', alpha=0.7)
    plt.title('Intensity Histogram')
    plt.xlabel('Pixel Value')
    plt.ylabel('Frequency')
    
    if is_uv and is_black_box:
        plt.axvspan(15, 200, alpha=0.2, color='green', label='Black box UV usable range')
        usable_signal = hist_norm[15:200].sum()
        plt.text(0.7, 0.9, f'Usable: {usable_signal:.2f}', transform=ax2.transAxes, 
                bbox=dict(boxstyle='round', facecolor='lightgreen'))
    elif is_uv:
        plt.axvspan(20, 180, alpha=0.2, color='orange', label='UV mid-range')
        mid_signal = hist_norm[20:180].sum()
        plt.text(0.7, 0.9, f'Mid-range: {mid_signal:.2f}', transform=ax2.transAxes,
                bbox=dict(boxstyle='round', facecolor='lightyellow'))
    
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    
    # 3. Sharpness analysis with environment-specific thresholds
    ax3 = plt.subplot(3, 4, 3)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = laplacian.var()
    plt.imshow(np.abs(laplacian), cmap='hot', aspect='equal')
    
    # Calculate scores for different thresholds
    if is_uv and is_black_box:
        if gray.mean() < 20:
            threshold = 30
            context = "Very Dark BB UV"
        elif gray.mean() < 50:
            threshold = 80
            context = "Dark BB UV"
        else:
            threshold = 150
            context = "Normal BB UV"
    elif is_uv:
        threshold = 50 if gray.mean() < 30 else 200
        context = "Open UV"
    else:
        threshold = 800
        context = "White Light"
        
    score = min(lap_var / threshold, 1.0) * 100
    plt.title(f'Laplacian (Sharpness)\nVar: {lap_var:.1f} | Score: {score:.1f}%\n{context} (thresh: {threshold})')
    plt.colorbar(shrink=0.6)
    plt.axis('off')
    
    # 4. Edge detection - Adaptive thresholds
    ax4 = plt.subplot(3, 4, 4)
    if gray.mean() < 30:
        edges = cv2.Canny(gray, 8, 25)
        edge_title = "Canny Edges (Low Thresh)"
    else:
        edges = cv2.Canny(gray, 15, 45)
        edge_title = "Canny Edges (Std Thresh)"
    
    edge_density = np.sum(edges > 0) / edges.size
    feature_score = min(edge_density * (8 if gray.mean() < 30 else 6), 1.0) * 100
    
    plt.imshow(edges, cmap='gray', aspect='equal')
    plt.title(f'{edge_title}\nDensity: {edge_density:.4f}\nFeature Score: {feature_score:.1f}%')
    plt.axis('off')
    
    # 5. ROI vs Background analysis
    ax5 = plt.subplot(3, 4, 5)
    if roi:
        x, y, w, h = roi
        # Ensure ROI is within bounds
        x = max(0, min(x, gray.shape[1] - w))
        y = max(0, min(y, gray.shape[0] - h))
        w = min(w, gray.shape[1] - x)
        h = min(h, gray.shape[0] - y)
        
        roi_img = gray[y:y+h, x:x+w]
        bg_mask = np.ones_like(gray, dtype=bool)
        bg_mask[y:y+h, x:x+w] = False
        background = gray[bg_mask]
        
        # Create visualization showing ROI and background
        roi_viz = gray.copy()
        roi_viz[y:y+h, x:x+w] = roi_viz[y:y+h, x:x+w] * 1.5  # Brighten ROI
        plt.imshow(roi_viz, cmap='gray', aspect='equal')
        
        roi_mean = roi_img.mean()
        bg_mean = background.mean()
        bg_std = background.std()
        sbr = roi_mean / (bg_mean + 1e-6)
        
        if bg_std > 0:
            cnr = abs(roi_mean - bg_mean) / bg_std
            sbr_score = min(cnr / 3, 1.0) * 100
        else:
            sbr_score = min(sbr / 2, 1.0) * 100
            
        plt.title(f'ROI vs Background\nROI: {roi_mean:.1f}, BG: {bg_mean:.1f}\nSBR: {sbr:.2f}, Score: {sbr_score:.1f}%')
        rect = plt.Rectangle((x, y), w, h, linewidth=2, edgecolor='red', facecolor='none')
        plt.gca().add_patch(rect)
    else:
        plt.imshow(gray, cmap='gray', aspect='equal')
        plt.title('No ROI specified')
    plt.axis('off')
    
    # 6. Illumination uniformity (for black box)
    ax6 = plt.subplot(3, 4, 6)
    if is_black_box:
        h_img, w_img = gray.shape
        # Create quadrant analysis
        q1 = gray[:h_img//2, :w_img//2].mean()
        q2 = gray[:h_img//2, w_img//2:].mean()
        q3 = gray[h_img//2:, :w_img//2].mean()
        q4 = gray[h_img//2:, w_img//2:].mean()
        
        quadrants = np.array([[q1, q2], [q3, q4]])
        
        im = plt.imshow(quadrants, cmap='viridis', aspect='equal')
        plt.title('Illumination Uniformity\n(Quadrant Means)')
        plt.colorbar(im, shrink=0.6)
        
        # Add text annotations
        for i in range(2):
            for j in range(2):
                plt.text(j, i, f'{quadrants[i,j]:.1f}', 
                        ha='center', va='center', color='white', fontweight='bold')
        
        quadrant_means = np.array([q1, q2, q3, q4])
        if quadrant_means.mean() > 5:
            illumination_cv = quadrant_means.std() / quadrant_means.mean()
            illumination_score = max(0, 1 - illumination_cv / 0.4) * 100
        else:
            illumination_score = 30
            
        plt.xlabel(f'CV: {illumination_cv if quadrant_means.mean() > 5 else "N/A":.3f}\nScore: {illumination_score:.1f}%')
    else:
        plt.imshow(gray, cmap='gray', aspect='equal')
        plt.title('Illumination Analysis\n(Black box only)')
    plt.axis('off')
    
    # 7. Contrast analysis
    ax7 = plt.subplot(3, 4, 7)
    rms_contrast = gray.std()
    
    # Environment-specific contrast thresholds
    if is_uv and is_black_box:
        if gray.mean() < 25:
            contrast_thresh = 12
        elif gray.mean() < 50:
            contrast_thresh = 20
        else:
            contrast_thresh = 25
    elif is_uv:
        contrast_thresh = 15 if gray.mean() < 30 else 30
    else:
        contrast_thresh = 60
        
    contrast_score = min(rms_contrast / contrast_thresh, 1.0) * 100
    
    # Show contrast visualization
    contrast_img = cv2.equalizeHist(gray)
    plt.imshow(contrast_img, cmap='gray', aspect='equal')
    plt.title(f'Contrast Enhanced\nRMS: {rms_contrast:.1f}\nScore: {contrast_score:.1f}%\nThresh: {contrast_thresh}')
    plt.axis('off')
    
    # 8. Exposure quality zones
    ax8 = plt.subplot(3, 4, 8)
    exposure_zones = np.zeros_like(gray)
    exposure_zones[gray < 16] = 1    # Underexposed
    exposure_zones[(gray >= 16) & (gray < 240)] = 2    # Good exposure
    exposure_zones[gray >= 240] = 3   # Overexposed
    
    colors = ['black', 'red', 'green', 'yellow']
    cmap = plt.matplotlib.colors.ListedColormap(colors)
    plt.imshow(exposure_zones, cmap=cmap, aspect='equal')
    plt.title('Exposure Zones')
    
    # Create custom legend
    from matplotlib.patches import Rectangle
    legend_elements = [Rectangle((0,0),1,1, facecolor='red', label='Underexposed'),
                      Rectangle((0,0),1,1, facecolor='green', label='Good'),
                      Rectangle((0,0),1,1, facecolor='yellow', label='Overexposed')]
    plt.legend(handles=legend_elements, loc='upper right', fontsize=8)
    plt.axis('off')
    
    # 9-12: Summary metrics
    ax9 = plt.subplot(3, 4, (9, 12))
    ax9.axis('off')
    
    # Calculate all metrics directly here
    try:
        # Calculate metrics using the same logic as the main function
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
        hist_norm = hist / hist.sum()
        
        # Sharpness calculation
        if is_uv and is_black_box:
            if gray.mean() < 20:
                sharpness_threshold = 30
            elif gray.mean() < 50:
                sharpness_threshold = 80
            else:
                sharpness_threshold = 150
        elif is_uv:
            sharpness_threshold = 50 if gray.mean() < 30 else 200
        else:
            sharpness_threshold = 800
        sharpness_score = min(lap_var / sharpness_threshold, 1.0) * 100
        
        # Exposure calculation
        if is_uv:
            total_signal = hist_norm[10:].sum()
            if is_black_box:
                usable_range = hist_norm[15:200].sum()
                severe_clip = hist_norm[250:].sum()
                if gray.mean() < 25:
                    exposure_score = min(total_signal * 1.5, 1.0) * 100
                else:
                    exposure_score = max(0.2, min(usable_range - severe_clip * 0.2, 1.0)) * 100
            else:
                mid_range_signal = hist_norm[20:180].sum()
                if gray.mean() < 30:
                    exposure_score = min(total_signal * 1.2, 1.0) * 100
                else:
                    high_clip_penalty = hist_norm[220:].sum() * 0.3
                    exposure_score = max(0.1, min(mid_range_signal - high_clip_penalty, 1.0)) * 100
        else:
            occupied_bins = np.sum(hist_norm > 0.005)
            exposure_score = min(occupied_bins / 200, 1.0) * 100
        
        # Contrast calculation  
        rms_contrast = gray.std()
        if is_uv and is_black_box:
            if gray.mean() < 25:
                contrast_threshold = 12
            elif gray.mean() < 50:
                contrast_threshold = 20
            else:
                contrast_threshold = 25
        elif is_uv:
            contrast_threshold = 15 if gray.mean() < 30 else 30
        else:
            contrast_threshold = 60
        contrast_score = min(rms_contrast / contrast_threshold, 1.0) * 100
        
        # SBR calculation
        sbr_score = 50  # default
        if roi:
            x, y, w, h = roi
            x = max(0, min(x, gray.shape[1] - w))
            y = max(0, min(y, gray.shape[0] - h))
            w = min(w, gray.shape[1] - x)
            h = min(h, gray.shape[0] - y)
            
            roi_img = gray[y:y+h, x:x+w]
            bg_mask = np.ones_like(gray, dtype=bool)
            bg_mask[y:y+h, x:x+w] = False
            background = gray[bg_mask]
            
            if background.size > 0 and roi_img.size > 0:
                roi_mean = roi_img.mean()
                bg_mean = background.mean()
                bg_std = background.std()
                
                if bg_std > 0:
                    cnr = abs(roi_mean - bg_mean) / bg_std
                    sbr_score = min(cnr / 3, 1.0) * 100
                else:
                    sbr = roi_mean / (bg_mean + 1e-6)
                    sbr_score = min(sbr / 2, 1.0) * 100
        
        # Feature detectability
        feature_score = 100
        if is_uv:
            if gray.mean() < 30:
                edges = cv2.Canny(gray, 8, 25)
                edge_density = np.sum(edges > 0) / edges.size
                feature_score = min(edge_density * 8, 1.0) * 100
            else:
                edges = cv2.Canny(gray, 15, 45)
                edge_density = np.sum(edges > 0) / edges.size
                feature_score = min(edge_density * 6, 1.0) * 100
        
        # Illumination uniformity
        illumination_score = 100
        if is_uv and is_black_box:
            h_img, w_img = gray.shape
            q1 = gray[:h_img//2, :w_img//2].mean()
            q2 = gray[:h_img//2, w_img//2:].mean()
            q3 = gray[h_img//2:, :w_img//2].mean()
            q4 = gray[h_img//2:, w_img//2:].mean()
            
            quadrant_means = np.array([q1, q2, q3, q4])
            if quadrant_means.mean() > 5:
                illumination_cv = quadrant_means.std() / quadrant_means.mean()
                illumination_score = max(0, 1 - illumination_cv / 0.4) * 100
            else:
                illumination_score = 30
        
        # Calculate overall score
        if is_uv and is_black_box:
            if gray.mean() < 25:
                overall_score = (
                    0.15 * sharpness_score +
                    0.35 * exposure_score +
                    0.20 * contrast_score +
                    0.10 * sbr_score +
                    0.15 * feature_score +
                    0.05 * illumination_score
                )
            else:
                overall_score = (
                    0.20 * sharpness_score +
                    0.25 * exposure_score +
                    0.20 * contrast_score +
                    0.15 * sbr_score +
                    0.15 * feature_score +
                    0.05 * illumination_score
                )
        elif is_uv:
            if gray.mean() < 30:
                overall_score = (
                    0.20 * sharpness_score +
                    0.35 * exposure_score +
                    0.25 * contrast_score +
                    0.10 * sbr_score +
                    0.10 * feature_score
                )
            else:
                overall_score = (
                    0.25 * sharpness_score +
                    0.30 * exposure_score +
                    0.20 * contrast_score +
                    0.15 * sbr_score +
                    0.10 * feature_score
                )
        else:
            overall_score = (
                0.40 * sharpness_score +
                0.25 * exposure_score +
                0.25 * contrast_score +
                0.10 * sbr_score
            )
        
        result = {
            'sharpness': sharpness_score,
            'exposure': exposure_score,
            'contrast': contrast_score,
            'sbr': sbr_score,
            'overall_score': overall_score
        }
        
        if is_uv:
            result['feature_detectability'] = feature_score
        if is_uv and is_black_box:
            result['illumination_uniformity'] = illumination_score
        
        metrics_text = f"""
QUALITY ASSESSMENT SUMMARY
{imaging_mode.upper()} imaging in {environment.replace('_', ' ').title()}

SCORES:
• Sharpness: {result['sharpness']:.1f}%
• Exposure: {result['exposure']:.1f}%  
• Contrast: {result['contrast']:.1f}%
• Signal-to-Background: {result['sbr']:.1f}%
"""
        
        if 'feature_detectability' in result:
            metrics_text += f"• Feature Detectability: {result['feature_detectability']:.1f}%\n"
        if 'illumination_uniformity' in result:
            metrics_text += f"• Illumination Uniformity: {result['illumination_uniformity']:.1f}%\n"
            
        metrics_text += f"\nOVERALL SCORE: {result['overall_score']:.1f}%"
        
        # Add quality interpretation
        overall_score = result['overall_score']
        if overall_score >= 80:
            quality = "EXCELLENT"
            color = 'green'
        elif overall_score >= 70:
            quality = "GOOD"
            color = 'darkgreen'
        elif overall_score >= 50:
            quality = "FAIR"
            color = 'orange'
        else:
            quality = "NEEDS IMPROVEMENT"
            color = 'red'
            
        metrics_text += f"\n\nQUALITY RATING: {quality}"
        
        ax9.text(0.1, 0.9, metrics_text, transform=ax9.transAxes, fontsize=12,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        ax9.text(0.1, 0.1, f"QUALITY RATING: {quality}", transform=ax9.transAxes, 
                fontsize=16, fontweight='bold', color=color,
                bbox=dict(boxstyle='round', facecolor='white', edgecolor=color, linewidth=2))
                
    except Exception as e:
        ax9.text(0.1, 0.5, f"Error calculating metrics: {str(e)}", 
                transform=ax9.transAxes, fontsize=12, color='red')
    
    plt.tight_layout()
    plt.show()
    
    # Print detailed analysis
    print(f"\n=== DETAILED ANALYSIS ===")
    print(f"Histogram Analysis:")
    hist_norm = hist / hist.sum()
    print(f"  Pixels in range 0-15: {hist_norm[0:16].sum():.3f}")
    if is_uv and is_black_box:
        print(f"  Pixels in usable range (15-200): {hist_norm[15:200].sum():.3f}")
    print(f"  Pixels in range 240-255: {hist_norm[240:256].sum():.3f}")
    
    print(f"\nSharpness Analysis:")
    print(f"  Laplacian variance: {lap_var:.2f}")
    print(f"  Threshold used: {threshold} ({context})")
    print(f"  Sharpness score: {score:.1f}%")
    
    if roi:
        print(f"\nROI Analysis:")
        print(f"  ROI coordinates: ({x}, {y}, {w}, {h})")
        print(f"  ROI mean: {roi_mean:.2f}")
        print(f"  Background mean: {bg_mean:.2f}")
        print(f"  Background std: {bg_std:.2f}")
        print(f"  Signal-to-background ratio: {sbr:.2f}")
        if bg_std > 0:
            print(f"  Contrast-to-noise ratio: {cnr:.2f}")
def image_quality_score(img, roi=None, imaging_mode='uv', environment='black_box'):
    """
    Compute an image quality score (0–100) optimized for UV and white light imaging.
    
    Parameters:
        img: OpenCV image (BGR format)
        roi (tuple): Optional region of interest (x, y, w, h)
        imaging_mode (str): 'uv' or 'white_light'
        environment (str): 'open' or 'black_box' - affects quality expectations
    
    Returns:
        dict: individual metrics + overall score
    """
    
    if img is None:
        raise ValueError("Image not found or cannot be read.")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    is_uv = imaging_mode.lower() == 'uv'
    is_black_box = environment.lower() == 'black_box'

    # 1. Sharpness (Variance of Laplacian) - adjusted for imaging mode and environment
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if is_uv and is_black_box:
        # Black box UV: More consistent lighting, can expect better sharpness
        if gray.mean() < 20:  # Very dark images
            threshold = 30
        elif gray.mean() < 50:  # Dark images
            threshold = 80
        else:
            threshold = 150  # Well-exposed black box UV
    elif is_uv:
        # Open environment UV
        if gray.mean() < 30:
            threshold = 50
        else:
            threshold = 200
    else:
        threshold = 800  # White light threshold
    
    sharpness_score = min(lap_var / threshold, 1.0)

    # 2. Exposure - mode-specific evaluation
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    hist_norm = hist / hist.sum()
    
    if is_uv:
        # UV exposure assessment - adapted for black box
        total_signal = hist_norm[10:].sum()  # Ignore complete black pixels
        
        if is_black_box:
            # Black box: Expect more controlled exposure
            # Look for reasonable signal distribution without severe clipping
            usable_range = hist_norm[15:200].sum()  # Broader usable range
            severe_clip = hist_norm[250:].sum()  # Only severe overexposure
            
            if gray.mean() < 25:  # Very dark
                # For very dark black box images, any detectable signal is good
                exposure_score = min(total_signal * 1.5, 1.0)
            else:
                # Standard black box assessment
                exposure_score = max(0.2, min(usable_range - severe_clip * 0.2, 1.0))
        else:
            # Open environment UV (original logic)
            mid_range_signal = hist_norm[20:180].sum()
            if gray.mean() < 30:
                exposure_score = min(total_signal * 1.2, 1.0)
            else:
                high_clip_penalty = hist_norm[220:].sum() * 0.3
                exposure_score = max(0.1, min(mid_range_signal - high_clip_penalty, 1.0))
    else:
        # White light: Prefer full dynamic range utilization
        occupied_bins = np.sum(hist_norm > 0.005)  # Slightly more sensitive threshold
        exposure_score = min(occupied_bins / 200, 1.0)  # Allow some headroom

    # 3. Contrast - adjusted for environment and imaging mode
    rms_contrast = gray.std()
    if is_uv and is_black_box:
        # Black box UV: More predictable contrast ranges
        if gray.mean() < 25:  # Very dark
            contrast_score = min(rms_contrast / 12, 1.0)  # Lower expectation
        elif gray.mean() < 50:  # Dark
            contrast_score = min(rms_contrast / 20, 1.0)
        else:
            contrast_score = min(rms_contrast / 25, 1.0)  # Better than open environment
    elif is_uv:
        # Open environment UV
        if gray.mean() < 30:
            contrast_score = min(rms_contrast / 15, 1.0)
        else:
            contrast_score = min(rms_contrast / 30, 1.0)
    else:
        contrast_score = min(rms_contrast / 60, 1.0)

    # 4. Signal-to-Background Ratio (critical for both modes)
    sbr_score = 0.5  # default mid-value
    if roi:
        x, y, w, h = roi
        
        # Ensure ROI is within image bounds
        x = max(0, min(x, gray.shape[1] - w))
        y = max(0, min(y, gray.shape[0] - h))
        w = min(w, gray.shape[1] - x)
        h = min(h, gray.shape[0] - y)
        
        roi_img = gray[y:y+h, x:x+w]
        
        # Create background mask excluding ROI
        bg_mask = np.ones_like(gray, dtype=bool)
        bg_mask[y:y+h, x:x+w] = False
        background = gray[bg_mask]

        if background.size > 0 and roi_img.size > 0:
            roi_mean = roi_img.mean()
            bg_mean = background.mean()
            bg_std = background.std()
            
            # Use contrast-to-noise ratio for better SBR assessment
            if bg_std > 0:
                cnr = abs(roi_mean - bg_mean) / bg_std
                sbr_score = min(cnr / 3, 1.0)  # Normalize CNR
            else:
                # Fallback to simple ratio
                sbr = roi_mean / (bg_mean + 1e-6)
                sbr_score = min(sbr / 2, 1.0)

    # 5. Additional UV-specific metric: Feature detectability and illumination quality
    feature_score = 1.0
    illumination_score = 1.0
    
    if is_uv:
        # Feature detectability assessment
        if gray.mean() < 30:
            edges = cv2.Canny(gray, 8, 25)  # Low thresholds for dark images
            edge_density = np.sum(edges > 0) / edges.size
            feature_score = min(edge_density * 8, 1.0)
        else:
            edges = cv2.Canny(gray, 15, 45)  # Standard thresholds
            edge_density = np.sum(edges > 0) / edges.size
            feature_score = min(edge_density * 6, 1.0)
        
        # Black box specific: Illumination uniformity assessment
        if is_black_box:
            # Assess illumination uniformity across the image
            h, w = gray.shape
            # Divide image into quadrants and check uniformity
            q1 = gray[:h//2, :w//2].mean()
            q2 = gray[:h//2, w//2:].mean()
            q3 = gray[h//2:, :w//2].mean()
            q4 = gray[h//2:, w//2:].mean()
            
            quadrant_means = np.array([q1, q2, q3, q4])
            if quadrant_means.mean() > 5:  # Avoid division by zero
                illumination_cv = quadrant_means.std() / quadrant_means.mean()
                illumination_score = max(0, 1 - illumination_cv / 0.4)  # Tolerate some variation
            else:
                illumination_score = 0.3  # Very dark, hard to assess

    # Weighted scoring - adjust for environment and imaging mode
    if is_uv and is_black_box:
        # Black box UV: Add illumination quality assessment
        if gray.mean() < 25:
            score = (
                0.15 * sharpness_score +
                0.35 * exposure_score +      # Critical for dark images
                0.20 * contrast_score +
                0.10 * sbr_score +
                0.15 * feature_score +       # Can features be detected?
                0.05 * illumination_score    # Illumination uniformity
            ) * 100
        else:
            score = (
                0.20 * sharpness_score +
                0.25 * exposure_score +
                0.20 * contrast_score +
                0.15 * sbr_score +
                0.15 * feature_score +
                0.05 * illumination_score
            ) * 100
    elif is_uv:
        # Open environment UV (original weighting)
        if gray.mean() < 30:
            score = (
                0.20 * sharpness_score +
                0.35 * exposure_score +
                0.25 * contrast_score +
                0.10 * sbr_score +
                0.10 * feature_score
            ) * 100
        else:
            score = (
                0.25 * sharpness_score +
                0.30 * exposure_score +
                0.20 * contrast_score +
                0.15 * sbr_score +
                0.10 * feature_score
            ) * 100
    else:
        # White light
        score = (
            0.40 * sharpness_score +
            0.25 * exposure_score +
            0.25 * contrast_score +
            0.10 * sbr_score
        ) * 100

    result = {
        "sharpness": float(round(sharpness_score * 100, 1)),
        "exposure": float(round(exposure_score * 100, 1)),
        "contrast": float(round(contrast_score * 100, 1)),
        "sbr": float(round(sbr_score * 100, 1)),
        "overall_score": float(round(score, 1)),
        "imaging_mode": imaging_mode,
        "environment": environment
    }
    
    if is_uv:
        result["feature_detectability"] = float(round(feature_score * 100, 1))
        if is_black_box:
            result["illumination_uniformity"] = float(round(illumination_score * 100, 1))
    
    return result

# Example usage:
# uv_result = image_quality_score(uv_image, roi=(100, 100, 200, 200), imaging_mode='uv')
# wl_result = image_quality_score(white_light_image, roi=(100, 100, 200, 200), imaging_mode='white_light')




# Download image from URL
url = "https://api.aflabox.ai/crop/image/7e673a45-2383-4a16-a573-ebc73e75ddd7?scale_type=original"
resp = requests.get(url, stream=True).content
img_array = np.asarray(bytearray(resp), dtype=np.uint8)
img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
manual=False


def draw_box(manual:bool):
    if manual:
        # Let user manually select ROI
        r = cv2.selectROI("Select ROI", img, fromCenter=False, showCrosshair=True)
        x, y, w, h = r

        # Draw rectangle for visualization
        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # Crop ROI
        roi_img = img[y:y+h, x:x+w]

        # Save outputs
        cv2.imwrite("maize_with_roi.png", img)       # image with bounding box
        cv2.imwrite("roi_only.png", roi_img)         # cropped ROI only

        # Save coordinates as JSON
        roi_coords = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
        with open("roi_coords.json", "w") as f:
            json.dump(roi_coords, f)

        cv2.imshow("ROI Selected", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Threshold for bright spots (fluorescence)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)

        # Find contours of bright regions
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        roi_list = []  # to save ROI details

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h > 500:  # ignore very small noise
                # Draw bounding box
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                
                # Save cropped ROI
                roi = img[y:y+h, x:x+w]
                fname = f"roi_{x}_{y}.png"
                cv2.imwrite(fname, roi)
                
                # Save coordinates
                roi_list.append({"x": x, "y": y, "w": w, "h": h, "file": fname})

        # Save image with all detected ROIs
        cv2.imwrite("maize_with_auto_roi.png", img)

        # Display
        cv2.imshow("Detected ROI", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        print("Saved ROIs:", roi_list)
# Use just the flexible Hough method with optimized parameters
def count_maize_kernels_optimized(img, roi=None, kernel_size_range=(100, 2500)):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
        roi_offset = (x, y)
    else:
        gray_roi = gray
        roi_offset = (0, 0)
    
    # Enhanced preprocessing
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(blurred)
    
    # Optimized Hough detection
    min_area, max_area = kernel_size_range
    min_radius = max(8, int(np.sqrt(min_area / np.pi) * 0.7))
    max_radius = min(80, int(np.sqrt(max_area / np.pi) * 1.2))
    
    circles = cv2.HoughCircles(enhanced, cv2.HOUGH_GRADIENT, 1, 10,
                              param1=45, param2=25,  # Optimized parameters
                              minRadius=min_radius, maxRadius=max_radius)
    
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        kernel_count = len(circles)
        centers = [(x + roi_offset[0], y + roi_offset[1]) for x, y, r in circles]
        return kernel_count, centers
    else:
        return 0, []

def test_hough_parameters(img, roi):
        """Test different Hough parameters to find optimal count"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if roi:
            x, y, w, h = roi
            gray_roi = gray[y:y+h, x:x+w]
        else:
            gray_roi = gray
        
        # Preprocessing
        blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(blurred)
        
        # Test different parameter combinations
        param_tests = [
            (40, 20, "Sensitive"),
            (45, 25, "Medium"), 
            (50, 30, "Conservative"),
            (35, 15, "Very Sensitive"),
            (55, 35, "Very Conservative")
        ]
        
        for param1, param2, desc in param_tests:
            circles = cv2.HoughCircles(enhanced, cv2.HOUGH_GRADIENT, 1, 10,
                                    param1=param1, param2=param2,
                                    minRadius=8, maxRadius=50)
            
            count = len(circles[0]) if circles is not None else 0
            print(f"{desc} (p1={param1}, p2={param2}): {count} kernels")
def count_maize_realistic(img, roi, min_area=200, max_area=2500):
    """Realistic maize counting without circular assumptions"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Otsu thresholding - good for bimodal distributions
    _, binary = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Gentle erosion to separate touching kernels
    kernel_sep = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    separated = cv2.erode(cleaned, kernel_sep, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(separated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_count = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            # Basic shape filtering
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                compactness = (perimeter ** 2) / (4 * np.pi * area)
                if compactness < 5.0:  # Not too elongated
                    valid_count += 1
    
    return valid_count

# Test this approach
def count_maize_higher_sensitivity(img, roi=None, min_area=80, max_area=2500):
    """Higher sensitivity method for dense maize kernel counting"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Less aggressive preprocessing
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    
    # Adaptive threshold instead of Otsu for better local adaptation
    adaptive_thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY_INV, 11, 3)
    
    # Minimal morphological cleaning to preserve small kernels
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    cleaned = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_OPEN, kernel_small, iterations=1)
    
    # Very gentle separation - don't lose small kernels
    kernel_sep = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    separated = cv2.erode(cleaned, kernel_sep, iterations=1)
    
    contours, _ = cv2.findContours(separated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_count = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:  # Lower minimum area
            valid_count += 1
    
    return valid_count
def refined_hough_count(img, roi):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    enhanced = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(enhanced)
    
    # Parameters between sensitive (40,20) and medium (45,25)
    circles = cv2.HoughCircles(enhanced, cv2.HOUGH_GRADIENT, 1, 8,  # Smaller min_distance
                              param1=42, param2=22,  # Between sensitive and medium
                              minRadius=5, maxRadius=40)
    
    return len(circles[0]) if circles is not None else 0

def count_no_separation(img, roi, min_area=50):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Just threshold and count - no morphological operations
    _, binary = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    return len([c for c in contours if cv2.contourArea(c) > min_area])
def count_maize_minimal_processing(img, roi=None, min_area=50, max_area=3000):
    """Minimal processing to preserve kernel detections"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Light blur only
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    
    # Adaptive threshold - better for local variations
    binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 15, 3)
    
    # Absolutely minimal cleaning - just remove single pixels
    kernel_tiny = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_tiny, iterations=1)
    
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_kernels = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            # Very basic shape filtering
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                compactness = (perimeter ** 2) / (4 * np.pi * area)
                if compactness < 8.0:  # Very lenient
                    valid_kernels.append(contour)
    
    return len(valid_kernels)
def count_maize_otsu_only(img, roi, min_area=40, max_area=3000):
    """Use only Otsu thresholding since it gave us 77 kernels"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Light preprocessing
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    
    # Otsu threshold (this worked!)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Very minimal cleaning
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_count = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            valid_count += 1
    
    return valid_count
def count_maize_aggressive_separation(img, roi, min_area=25, max_area=4000):
    """More aggressive separation to find touching kernels"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    
    # Otsu threshold (this works!)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Distance transform for separation
    dist_transform = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    
    # Find local maxima more aggressively
    _, sure_fg = cv2.threshold(dist_transform, 0.3*dist_transform.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)
    
    # Connected components to separate touching objects
    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    
    # Mark unknown region
    unknown = cv2.subtract(binary, sure_fg)
    markers[unknown == 255] = 0
    
    # Watershed
    img_3channel = cv2.cvtColor(gray_roi, cv2.COLOR_GRAY2BGR)
    markers = cv2.watershed(img_3channel, markers)
    
    # Count separated regions
    unique_markers = np.unique(markers)
    valid_count = 0
    
    for marker_id in unique_markers:
        if marker_id <= 1:  # Skip background and boundaries
            continue
            
        # Create mask for this marker
        marker_mask = np.zeros_like(binary)
        marker_mask[markers == marker_id] = 255
        
        # Check size
        area = np.sum(marker_mask == 255)
        if min_area <= area <= max_area:
            valid_count += 1
    
    return valid_count
def count_maize_absolute_minimal(img, roi):
    """Absolute minimal processing - no blur, no filtering"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # NO preprocessing at all - raw Otsu
    _, binary = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"Raw Otsu (no blur): {len(contours)} contours")
    
    # Test including internal holes
    contours_all, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    external_contours = []
    
    if hierarchy is not None:
        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:  # No parent - external contour
                external_contours.append(contours_all[i])
    
    print(f"External contours only: {len(external_contours)}")
    print(f"All contours including holes: {len(contours_all)}")
    
    return len(contours)

def count_maize_ultra_permissive(img, roi):
    """Ultra permissive - minimal filtering"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Minimal preprocessing
    blurred = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    
    # Otsu threshold (our winner)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # NO morphological operations - skip cleaning entirely
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Test different minimum area thresholds
    area_tests = [1, 5, 10, 15, 20, 25]
    
    for min_area in area_tests:
        count = len([c for c in contours if cv2.contourArea(c) >= min_area])
        print(f"Min area {min_area}: {count} kernels")
    
    # Also test without ANY size filtering
    total_contours = len(contours)
    print(f"All contours (no size filter): {total_contours}")
    
    return contours
def count_maize_final(img, roi=None, min_area=5):
    """Final optimized maize kernel counting - no blur!"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    # Raw Otsu threshold - NO preprocessing
    _, binary = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Optional minimal size filtering to remove tiny noise
    if min_area > 0:
        valid_contours = [c for c in contours if cv2.contourArea(c) >= min_area]
        return len(valid_contours), valid_contours
    else:
        return len(contours), contours


def analyze_kernel_sizes(img, roi):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
    else:
        gray_roi = gray
    
    _, binary = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    areas = [cv2.contourArea(c) for c in contours]
    areas.sort()
    
    print(f"Total objects: {len(areas)}")
    print(f"Size range: {min(areas):.0f} - {max(areas):.0f} pixels")
    print(f"Median size: {areas[len(areas)//2]:.0f} pixels")
    
    # Show size distribution
    ranges = [(0,1), (1,5), (5,10), (10,25), (25,50), (50,100), (100,500), (500,float('inf'))]
    for min_size, max_size in ranges:
        if max_size == float('inf'):
            count = len([a for a in areas if a >= min_size])
            print(f"Size {min_size}+: {count} objects")
        else:
            count = len([a for a in areas if min_size <= a < max_size])
            print(f"Size {min_size}-{max_size}: {count} objects")
def visualize_maize_kernels(img, roi=None, show_contours=True, show_centers=True, show_numbers=False):
    """
    Visualize detected maize kernels with color coding by size category
    
    Parameters:
        img: Input image
        roi: Region of interest (x, y, w, h)
        show_contours: Whether to draw contour boundaries
        show_centers: Whether to draw center points
        show_numbers: Whether to number each detection
    
    Returns:
        Visualization results and statistics
    """
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply ROI
    if roi:
        x, y, w, h = roi
        gray_roi = gray[y:y+h, x:x+w]
        roi_offset = (x, y)
    else:
        gray_roi = gray
        roi_offset = (0, 0)
        x, y = 0, 0
    
    # Raw Otsu threshold (our best method)
    _, binary = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Create visualization image
    result_img = img.copy()
    
    # Define size categories and colors
    size_categories = {
        'noise': {'range': (0, 5), 'color': (128, 128, 128), 'name': 'Noise/Artifacts'},      # Gray
        'tiny': {'range': (5, 25), 'color': (255, 0, 255), 'name': 'Tiny Objects'},          # Magenta  
        'small': {'range': (25, 100), 'color': (0, 255, 255), 'name': 'Small Kernels'},      # Cyan
        'medium': {'range': (100, 500), 'color': (0, 255, 0), 'name': 'Medium Kernels'},     # Green
        'large': {'range': (500, 2000), 'color': (255, 165, 0), 'name': 'Large Kernels'},    # Orange
        'huge': {'range': (2000, float('inf')), 'color': (0, 0, 255), 'name': 'Merged Kernels'} # Red
    }
    
    # Categorize and draw objects
    categorized_objects = {cat: [] for cat in size_categories.keys()}
    
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        
        # Determine category
        category = None
        for cat_name, cat_info in size_categories.items():
            min_size, max_size = cat_info['range']
            if min_size <= area < max_size:
                category = cat_name
                break
        
        if category is None:
            category = 'huge'  # Fallback for very large objects
        
        # Adjust contour coordinates for full image
        contour_full = contour + np.array([roi_offset], dtype=contour.dtype)
        
        # Calculate center
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"]) + roi_offset[0]
            cy = int(M["m01"] / M["m00"]) + roi_offset[1]
        else:
            cx, cy = roi_offset[0], roi_offset[1]
        
        # Store object info
        categorized_objects[category].append({
            'contour': contour_full,
            'center': (cx, cy),
            'area': area,
            'id': i
        })
        
        # Get color for this category
        color = size_categories[category]['color']
        
        # Draw contour outline
        if show_contours:
            cv2.drawContours(result_img, [contour_full], -1, color, 2)
        
        # Draw center point
        if show_centers:
            cv2.circle(result_img, (cx, cy), 4, color, -1)
            cv2.circle(result_img, (cx, cy), 6, (255, 255, 255), 1)  # White border
        
        # Draw numbers
        if show_numbers:
            cv2.putText(result_img, str(i+1), (cx-8, cy-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Add ROI rectangle
    if roi:
        cv2.rectangle(result_img, (x, y), (x+w, y+h), (255, 255, 255), 3)
        cv2.putText(result_img, 'ROI', (x+5, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Create detailed visualization
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Original image
    axes[0,0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0,0].set_title('Original Image')
    axes[0,0].axis('off')
    
    # Detection results
    axes[0,1].imshow(cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB))
    axes[0,1].set_title('Detected Objects (Color Coded by Size)')
    axes[0,1].axis('off')
    
    # Binary threshold result
    if roi:
        binary_display = np.zeros_like(gray)
        binary_display[y:y+h, x:x+w] = binary
    else:
        binary_display = binary
    axes[1,0].imshow(binary_display, cmap='gray')
    axes[1,0].set_title('Binary Threshold (Otsu)')
    axes[1,0].axis('off')
    
    # Statistics and legend
    axes[1,1].axis('off')
    
    # Create legend and statistics
    total_objects = sum(len(objs) for objs in categorized_objects.values())
    
    legend_text = "DETECTION RESULTS\n\n"
    legend_text += f"Total Objects: {total_objects}\n"
    legend_text += f"ROI: {roi if roi else 'Full image'}\n\n"
    
    legend_text += "SIZE CATEGORIES:\n"
    y_pos = 0.85
    
    for cat_name, cat_info in size_categories.items():
        count = len(categorized_objects[cat_name])
        color_rgb = [c/255.0 for c in cat_info['color'][::-1]]  # Convert BGR to RGB and normalize
        
        # Add colored square
        rect = plt.Rectangle((0.02, y_pos-0.02), 0.03, 0.03, 
                           facecolor=color_rgb, transform=axes[1,1].transAxes)
        axes[1,1].add_patch(rect)
        
        legend_text += f"  {cat_info['name']}: {count}\n"
        if count > 0:
            areas = [obj['area'] for obj in categorized_objects[cat_name]]
            avg_area = np.mean(areas)
            legend_text += f"    (avg: {avg_area:.0f} px²)\n"
        
        y_pos -= 0.08
    
    # Calculate kernel estimates
    legitimate_kernels = (len(categorized_objects['small']) + 
                         len(categorized_objects['medium']) + 
                         len(categorized_objects['large']) + 
                         len(categorized_objects['huge']))
    
    # Estimate for merged kernels (assume large/huge objects might be multiple kernels)
    large_objects = len(categorized_objects['large']) + len(categorized_objects['huge'])
    estimated_total = legitimate_kernels + large_objects  # Assume some large objects are 2 kernels
    
    legend_text += f"\nKERNEL ESTIMATES:\n"
    legend_text += f"Conservative: {legitimate_kernels} kernels\n"
    legend_text += f"Liberal: {estimated_total} kernels\n"
    legend_text += f"(Assuming some large objects\nare multiple touching kernels)"
    
    axes[1,1].text(0.1, 0.95, legend_text, transform=axes[1,1].transAxes, 
                  fontsize=10, verticalalignment='top', fontfamily='monospace',
                  bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    plt.tight_layout()
    plt.show()
    
    # Print detailed statistics
    print("DETAILED OBJECT ANALYSIS:")
    print("=" * 50)
    
    for cat_name, cat_info in size_categories.items():
        objects = categorized_objects[cat_name]
        if objects:
            print(f"\n{cat_info['name'].upper()}:")
            print(f"  Count: {len(objects)}")
            areas = [obj['area'] for obj in objects]
            print(f"  Size range: {min(areas):.0f} - {max(areas):.0f} pixels²")
            print(f"  Average size: {np.mean(areas):.0f} pixels²")
            
            # Show locations of a few examples
            if len(objects) <= 5:
                print("  Locations:", [f"({obj['center'][0]}, {obj['center'][1]})" for obj in objects])
            else:
                print("  Example locations:", [f"({obj['center'][0]}, {obj['center'][1]})" for obj in objects[:3]], "...")
    
    return {
        'result_image': result_img,
        'categorized_objects': categorized_objects,
        'total_count': total_objects,
        'legitimate_kernels': legitimate_kernels,
        'estimated_total': estimated_total
    }
# Example usage
if __name__ == "__main__":
    roi=your_roi=(122,1,1679,1068) #{"x": 122, "y": 1, "w": 1679, "h": 1068}
    # metrics = diagnose_image_quality(img,roi) #roi=(50,50,100,100)
    # print(metrics)
    # Compare methods:
    # results = count_maize_kernels(img, roi=roi, 
    #                          imaging_mode='uv', environment='black_box',
    #                          kernel_size_range=(100, 2500))
    # print(f"Maize kernels detected: {results['kernel_count']}")
    # print("Method comparison:", results['method_comparison'])
    
 

    # Run this to see which parameters work best
    # realistic_count = count_maize_realistic(img, roi, min_area=150, max_area=2000)
    # print(f"Realistic maize count: {realistic_count}")
    # area_tests = [
    #     (100, 2000),   # More permissive
    #     (150, 2000),   # Current realistic method
    #     (200, 2000),   # More restrictive
    #     (100, 1500),   # Smaller max size
    #     (150, 2500),   # Larger max size
    # ]

    # print("Area threshold sensitivity:")
    # for min_area, max_area in area_tests:
    #     count = count_maize_realistic(img, roi, min_area=min_area, max_area=max_area)
    #     print(f"Area {min_area}-{max_area}: {count} kernels")
    
    # sensitivity_tests = [
    #     (60, 2500, "Very High Sensitivity"),
    #     (80, 2500, "High Sensitivity"),  
    #     (100, 2500, "Medium Sensitivity"),
    #     (120, 2500, "Lower Sensitivity")
    # ]

    # for min_area, max_area, desc in sensitivity_tests:
    #     count = count_maize_higher_sensitivity(img, roi, min_area, max_area)
    #     print(f"{desc} (min_area={min_area}): {count} kernels")
        
    # refined_count = refined_hough_count(img, roi)
    # print(f"Refined Hough count: {refined_count}")
    
    # very_permissive_count = count_maize_higher_sensitivity(img, your_roi, 
    #                                                   min_area=20,    # Much smaller
    #                                                   max_area=5000)  # Much larger
    # print(f"Very permissive count: {very_permissive_count}")
    # no_sep_count = count_no_separation(img, your_roi, min_area=30)
    # print(f"No separation count: {no_sep_count}")
    # area_tests = [
    #     (30, 3000),
    #     (40, 3000), 
    #     (50, 3000),
    #     (60, 3000),
    #     (70, 3000),
    # ]

    # print("Minimal processing with different area filters:")
    # for min_area, max_area in area_tests:
    #     count = count_maize_minimal_processing(img, your_roi, min_area, max_area)
    #     print(f"Min area {min_area}: {count} kernels")
    
    # otsu_count = count_maize_otsu_only(img, your_roi, min_area=40)
    # print(f"Otsu-based count: {otsu_count}")
    # Test aggressive separation
    # aggressive_count = count_maize_aggressive_separation(img, your_roi)
    # print(f"Aggressive separation count: {aggressive_count}")

    # # Also test with more permissive size filtering on our best method
    # permissive_sizes = [
    #     (20, 5000),
    #     (30, 4000), 
    #     (40, 3000),
    #     (25, 3500)
    # ]

    # print("\nOtsu method with different size filters:")
    # for min_area, max_area in permissive_sizes:
    #     count = count_maize_otsu_only(img, your_roi, min_area=min_area, max_area=max_area)
    #     print(f"Area {min_area}-{max_area}: {count} kernels")
    # contours = count_maize_ultra_permissive(img, your_roi)
    # raw_count = count_maize_absolute_minimal(img, your_roi)
    
    # # Your final count
    # final_count, final_contours = count_maize_final(img, your_roi, min_area=3)
    # print(f"Final maize kernel count: {final_count}")

    # # Test different minimal filtering
    # for min_area in [0, 1, 3, 5, 10]:
    #     count, _ = count_maize_final(img, your_roi, min_area=min_area)
    #     print(f"Min area {min_area}: {count} kernels")
    # analyze_kernel_sizes(img, your_roi)
    # print(contours)
    results = visualize_maize_kernels(img, roi=your_roi, 
                                     show_contours=True, 
                                     show_centers=True, 
                                     show_numbers=False)
    
    print(f"Total detected objects: {results['total_count']}")
    print(f"Estimated kernel count: {results['estimated_total']}")