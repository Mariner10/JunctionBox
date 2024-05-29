def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb_color):
    return '#{:02x}{:02x}{:02x}'.format(*rgb_color)

def interpolate_color(color1, color2, factor):
    return tuple(int(c1 + (c2 - c1) * factor) for c1, c2 in zip(color1, color2))

def get_gradient_color(color_low, color_mid, color_high, value):
    """Get the color for a given integer value between 0 and 100."""

    rgb_start = hex_to_rgb(color_low)
    rgb_middle = hex_to_rgb(color_mid)
    rgb_end = hex_to_rgb(color_high)
    
    if value <= 50:
        factor = value / 50
        interpolated_color = interpolate_color(rgb_start, rgb_middle, factor)
    else:
        factor = (value - 50) / 50
        interpolated_color = interpolate_color(rgb_middle, rgb_end, factor)

    return rgb_to_hex(interpolated_color)
