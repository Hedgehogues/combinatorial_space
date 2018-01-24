import numpy as np
import cv2

# Получаем коды изображения во всех возможных контекстах
def get_shift_context(image, flatten_code=True, flatten_context=True):
    context_codes = []
    window_size = np.array(image).shape
    for context_y in np.arange(-window_size[0]+1, window_size[0], 1):
        if not flatten_context:
            context_codes.append([])
        for context_x in np.arange(-window_size[1]+1, window_size[1], 1):
            context_number = [context_y, context_x]
            context_image = get_context_image(context_number=context_number, image=image)
            context_code = get_codes(context_image)
            if not flatten_context:
                context_codes[-1].append(context_code.flatten() if flatten_code else context_code)
            else:
                context_codes.append(context_code.flatten() if flatten_code else context_code)
    return context_codes

def get_context_image(context_number, image):
    dx = context_number[1]
    dy = context_number[0]
    x_context_image = np.zeros(image.shape)
    context_image = np.zeros(image.shape)
    
    # Формируем изображение в новом контексте
    if dx < 0:
        x_context_image[:, -dx:] = image[:, :dx]
    elif dx == 0:
        x_context_image = image
    else:
        x_context_image[:, :-dx] = image[:, dx:]
    if dy < 0:
        context_image[-dy:, :] = x_context_image[:dy, :]
    elif dy == 0:
        context_image = x_context_image
    else:
        context_image[:-dy, :] = x_context_image[dy:, :]
        
    return np.uint8(context_image)

# Получаем код изображения
def get_codes(image, count_directs=16, width_angle=np.pi/2, strength_threshould=0):
    sobel_x = cv2.Sobel(image,cv2.CV_32F,1,0,ksize=1)
    sobel_y = cv2.Sobel(image,cv2.CV_32F,0,1,ksize=1)
    
    start_angle = 0
    finish_angle = 2*np.pi
    
    step_angle = (finish_angle - start_angle) / count_directs
    central_angle = np.arange(start_angle, finish_angle, step_angle) + width_angle/2
    
    gamma_down = central_angle - width_angle/2
    gamma_up = central_angle + width_angle/2
    
    angle = np.arctan2(sobel_y, sobel_x) + np.pi
    strength = np.sqrt(sobel_y**2 + sobel_x**2)
    
    return np.array([
        np.uint(
            (
                (gamma_down[i] <= angle) & (angle <= gamma_up[i]) & (gamma_up[i] <= 2*np.pi) |
                (0 <= angle) & (angle <= gamma_up[i] - 2*np.pi) & (gamma_up[i] > 2*np.pi)
            )
            &
            (strength > strength_threshould)
        )
        for i in range(0, count_directs)
    ])